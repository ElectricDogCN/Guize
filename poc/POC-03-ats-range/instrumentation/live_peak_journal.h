// Private Linux diagnostic sink. Include live_buffer_accounting.h first.
#pragma once
#include <cerrno>
#include <climits>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

namespace guize_live_buffer {
class PeakJournal {
  int fd_=-1;
  pid_t owner_=0;
  uint64_t birth_=0,sequence_=0,previousPeak_=0;
  bool healthy_=false;
  static constexpr uint64_t RecordLimit=4096;

  static uint64_t process_birth() {
    char raw[4097];int fd=open("/proc/self/stat",O_RDONLY|O_CLOEXEC);
    if(fd<0)return 0;
    const auto size=read(fd,raw,sizeof(raw)-1);close(fd);
    if(size<=0||size>=ssize_t(sizeof(raw)-1))return 0;
    raw[size]=0;char *cursor=strrchr(raw,')');if(!cursor)return 0;
    ++cursor;
    for(unsigned field=0;field<19;++field) {
      while(*cursor==' ')++cursor;
      if(!*cursor)return 0;
      while(*cursor&&*cursor!=' ')++cursor;
    }
    while(*cursor==' ')++cursor;
    char *end=nullptr;errno=0;auto value=strtoull(cursor,&end,10);
    return errno||end==cursor||(*end!=' '&&*end!='\n')?0:value;
  }
public:
  explicit PeakJournal(const char *path) {
    owner_=getpid();birth_=process_birth();
    if(!path||path[0]!='/'||geteuid()==0||!birth_)return;
    char resolved[PATH_MAX];
    if(!realpath(path,resolved)||strcmp(path,resolved))return;
    int directory=open(path,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if(directory<0)return;
    struct stat meta{};
    if(fstat(directory,&meta)||meta.st_uid!=geteuid()||(meta.st_mode&0777)!=0700) { close(directory);return; }
    char name[96];const auto n=snprintf(name,sizeof(name),"peak-%ld-%llu.jsonl",long(owner_),static_cast<unsigned long long>(birth_));
    if(n<=0||size_t(n)>=sizeof(name)) { close(directory);return; }
    fd_=openat(directory,name,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
    // Retain any failed/partial file. Never replace an earlier PID/exec epoch.
    healthy_=fd_>=0&&fsync(directory)==0;close(directory);
  }
  PeakJournal(const PeakJournal &)=delete;
  PeakJournal &operator=(const PeakJournal &)=delete;
  ~PeakJournal() { if(fd_>=0)close(fd_); }
  bool healthy() const { return healthy_; }
  bool publish(const Snapshot &state) {
    if(!healthy_||getpid()!=owner_||sequence_>=RecordLimit||state.generation||state.abiVersion!=1||
       state.violations||state.uncoveredExternalEvents||state.peakBytes<state.currentBytes||
       (sequence_==0&&(state.peakBytes||state.currentBytes))||
       (sequence_>0&&state.peakBytes<=previousPeak_)) { healthy_=false;return false; }
    timespec clock{};
    if(clock_gettime(CLOCK_MONOTONIC,&clock)) { healthy_=false;return false; }
    const auto now=uint64_t(clock.tv_sec)*1000000000+uint64_t(clock.tv_nsec);
    char raw[2048];
    const auto n=snprintf(raw,sizeof(raw),
      "{\"kind\":\"INSTRUMENTED_ATS_DURABLE_PEAK\",\"schemaVersion\":1,\"pid\":%ld,\"startTicks\":%llu,"
      "\"sequence\":%llu,\"abiVersion\":1,\"generation\":0,\"accountingWindow\":\"process-lifetime\","
      "\"beforeMonotonicNs\":%llu,\"peakBytes\":%llu,\"currentBytes\":%llu,"
      "\"currentByKind\":[%llu,%llu,%llu,%llu],\"acquisitions\":[%llu,%llu,%llu,%llu],"
      "\"releases\":[%llu,%llu,%llu,%llu],\"violations\":0,\"uncoveredExternalEvents\":0}\n",
      long(owner_),static_cast<unsigned long long>(birth_),static_cast<unsigned long long>(sequence_),
      static_cast<unsigned long long>(now),static_cast<unsigned long long>(state.peakBytes),
      static_cast<unsigned long long>(state.currentBytes),
      static_cast<unsigned long long>(state.currentByKind[0]),static_cast<unsigned long long>(state.currentByKind[1]),
      static_cast<unsigned long long>(state.currentByKind[2]),static_cast<unsigned long long>(state.currentByKind[3]),
      static_cast<unsigned long long>(state.acquisitions[0]),static_cast<unsigned long long>(state.acquisitions[1]),
      static_cast<unsigned long long>(state.acquisitions[2]),static_cast<unsigned long long>(state.acquisitions[3]),
      static_cast<unsigned long long>(state.releases[0]),static_cast<unsigned long long>(state.releases[1]),
      static_cast<unsigned long long>(state.releases[2]),static_cast<unsigned long long>(state.releases[3]));
    if(n<=0||size_t(n)>=sizeof(raw)) { healthy_=false;return false; }
    size_t offset=0;
    while(offset<size_t(n)) {
      const auto written=write(fd_,raw+offset,size_t(n)-offset);
      if(written<0&&errno==EINTR)continue;
      if(written<=0) { healthy_=false;return false; }
      offset+=size_t(written);
    }
    if(fsync(fd_)) { healthy_=false;return false; }
    previousPeak_=state.peakBytes;++sequence_;return true;
  }
  static bool sink(void *context,const Snapshot &state) {
    return static_cast<PeakJournal *>(context)->publish(state);
  }
};

// Private instrumented-core adapter. Failure terminates this diagnostic epoch
// before the callsite is allowed to acquire payload; no core dump is requested.
class DurableAccounting {
  pid_t owner_;
  PeakJournal journal_;
  Ledger ledger_;
  [[noreturn]] static void fail() {
    const char message[]="guize durable accounting epoch invalid\n";
    const auto ignored=write(STDERR_FILENO,message,sizeof(message)-1);(void)ignored;
    _exit(70);
  }
  void require_owner() const { if(getpid()!=owner_)fail(); }
public:
  explicit DurableAccounting(const char *directory):owner_(getpid()),journal_(directory),ledger_(PeakJournal::sink,&journal_) {
    if(!journal_.healthy()||!journal_.publish(Snapshot{}))fail();
  }
  void acquire(unsigned kind,uint64_t bytes) {
    require_owner();
    // External payload already exists before this attachment. Reject the whole
    // epoch; this does not pretend that its earlier allocation was observed.
    if(kind==EXTERNAL||!ledger_.acquire(kind,bytes))fail();
  }
  void release(unsigned kind,uint64_t bytes) {
    require_owner();if(!ledger_.release(kind,bytes))fail();
  }
  Snapshot snapshot(unsigned resetWindow=0) {
    require_owner();if(resetWindow)fail();return ledger_.snapshot();
  }
};
} // namespace guize_live_buffer
