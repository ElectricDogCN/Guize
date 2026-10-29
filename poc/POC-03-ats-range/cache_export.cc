// ATS 9.2.3 isolated POC observer. No HTTP fetch, cache write or disk-format parsing.
#include <ts/ts.h>
#include <ts/experimental.h>
#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <ctime>
#include <deque>
#include <fcntl.h>
#include <mutex>
#include <regex>
#include <set>
#include <sstream>
#include <string>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <vector>

namespace {
constexpr uint64_t ObjectLimit=64ULL<<20, TotalLimit=512ULL<<20;
constexpr size_t KeyLimit=512, RequestKeys=128, RequestLimit=8;
std::string utc() {
  timespec now{};clock_gettime(CLOCK_REALTIME,&now);tm value{};gmtime_r(&now.tv_sec,&value);
  char text[40];strftime(text,sizeof(text),"%Y-%m-%dT%H:%M:%SZ",&value);return text;
}
struct Key { unsigned id; std::string url, observedAt; };
struct Read {
  TSCont cont=nullptr; TSCacheKey key=nullptr; TSVConn vc=nullptr;
  TSIOBuffer buffer=nullptr; TSIOBufferReader reader=nullptr;
  TSVIO vio=nullptr;
  TSAction action=nullptr; bool opening=true, done=false;
  int fd=-1; Key item; int64_t expected=-1; uint64_t bytes=0;
  std::string startedAt;
  std::chrono::steady_clock::time_point started;
};
struct Event { Read *read; TSEvent event; void *data; };
struct State {
  int directory=-1, lookups=-1, lookupEvents=-1, events=-1, job=-1, results=-1;
  std::mutex catalogMutex; std::vector<Key> keys; size_t journaled=0;
  TSCont work=nullptr; TSMutex mutex=nullptr; bool scheduled=false, disabled=false, cacheReady=false;
  std::deque<Event> pending; std::vector<Key> assigned; size_t next=0;
  Read *active=nullptr; uint64_t total=0; unsigned controls=0, jobs=0;
} s;
std::string quote(const std::string &v) {
  std::string out="\"";
  for(unsigned char c:v) { if(c=='"'||c=='\\')out+='\\'; if(c<32)out+='?';else out+=c; }
  return out+'"';
}
bool write_all(int fd,const char *p,size_t n) {
  while(n) { ssize_t x=write(fd,p,n); if(x<0&&errno==EINTR)continue; if(x<=0)return false; p+=x;n-=x; }
  return true;
}
bool line(int fd,const std::string &v) { auto x=v+"\n";return write_all(fd,x.data(),x.size()); }
int create(int directory,const std::string &name) {
  return openat(directory,name.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
}
void schedule() { if(!s.scheduled) { s.scheduled=true; TSContScheduleOnPool(s.work,0,TS_THREAD_POOL_TASK); } }
void flush_catalog() {
  std::lock_guard<std::mutex> lock(s.catalogMutex);
  while(s.journaled<s.keys.size()) {
    const auto &k=s.keys[s.journaled++];
    if(!line(s.lookups,"{\"keyId\":"+std::to_string(k.id)+",\"lookupUrl\":"+quote(k.url)+",\"observedAt\":"+quote(k.observedAt)+"}"))s.disabled=true;
  }
}
int capture(TSCont,TSEvent,void *data) {
  TSHttpTxn txn=static_cast<TSHttpTxn>(data);
  std::string requestId; TSMBuffer requestBuffer=nullptr; TSMLoc requestHeader=TS_NULL_MLOC;
  if(TSHttpTxnClientReqGet(txn,&requestBuffer,&requestHeader)==TS_SUCCESS) {
    TSMLoc field=TSMimeHdrFieldFind(requestBuffer,requestHeader,"X-Lab-Request-ID",-1);
    if(field!=TS_NULL_MLOC) {
      int length=0;const char *value=TSMimeHdrFieldValueStringGet(requestBuffer,requestHeader,field,-1,&length);
      if(value&&length==32) {
        std::string candidate(value,length);
        if(std::regex_match(candidate,std::regex("[a-f0-9]{32}")))requestId=candidate;
      }
      TSHandleMLocRelease(requestBuffer,requestHeader,field);
    }
    TSHandleMLocRelease(requestBuffer,TS_NULL_MLOC,requestHeader);
  }
  int lookupStatus=-1;
  bool statusAvailable=TSHttpTxnCacheLookupStatusGet(txn,&lookupStatus)==TS_SUCCESS;
  TSMBuffer b=TSMBufferCreate(); TSMLoc u=TS_NULL_MLOC;
  if(TSUrlCreate(b,&u)==TS_SUCCESS) {
    if(TSHttpTxnCacheLookupUrlGet(txn,b,u)==TS_SUCCESS) {
      int n=0;char *p=TSUrlStringGet(b,u,&n);
      if(p) {
        // Fixed private origin, context, two immutable source versions, optional CRR Range suffix.
        static const std::regex allowed(R"(^http://(127\.0\.0\.1:18231|ats\.local(:80)?)/ctx/[0-9a-f]{32}/(base|changed)/object\.bin(-bytes=[0-9]{1,20}-[0-9]{1,20})?$)");
        if(n>0&&n<=1024) {
          std::string url(p,n);
          if(std::regex_match(url,allowed)) {
            std::lock_guard<std::mutex> lock(s.catalogMutex);
            // Retain EVERY observed protected lookup, including repeated hits.
            // The separate unique-key catalogue is only for explicit exports.
            if(!line(s.lookupEvents,"{\"requestId\":"+quote(requestId)+",\"lookupUrl\":"+quote(url)+
                ",\"observedAt\":"+quote(utc())+",\"nativeLookupStatus\":"+std::to_string(lookupStatus)+
                ",\"statusAvailable\":"+(statusAvailable?"true":"false")+"}"))s.disabled=true;
            bool exists=std::any_of(s.keys.begin(),s.keys.end(),[&](const Key &k){return k.url==url;});
            if(!exists&&s.keys.size()<KeyLimit)s.keys.push_back({unsigned(s.keys.size()+1),url,utc()});
          }
        }
        TSfree(p);
      }
    }
    TSHandleMLocRelease(b,TS_NULL_MLOC,u);
  }
  TSMBufferDestroy(b); TSHttpTxnReenable(txn,TS_EVENT_HTTP_CONTINUE);return 0;
}
// Cache callbacks only enqueue; bounded file IO is performed by the task-pool continuation.
int cache_event(TSCont cont,TSEvent event,void *data) {
  auto *r=static_cast<Read *>(TSContDataGet(cont));
  if(!r->done) { s.pending.push_back({r,event,data});schedule(); }
  return 0;
}
void finish(Read *r,const std::string &status,const std::string &reason) {
  if(r->done)return;
  r->done=true;
  if(r->opening&&r->action&&!TSActionDone(r->action))TSActionCancel(r->action);
  if(r->vc) { if(status=="exported")TSVConnClose(r->vc);else TSVConnAbort(r->vc,0);r->vc=nullptr; }
  bool saved=r->fd>=0;
  if(saved) { if(fsync(r->fd)!=0)saved=false; if(close(r->fd)!=0)saved=false;r->fd=-1; }
  std::string part="key-"+std::to_string(r->item.id)+".body.part", body="key-"+std::to_string(r->item.id)+".body";
  std::string outcome=status, detail=reason;
  if(status=="exported") {
    // linkat provides exclusive final publication; no existing export may be overwritten.
    if(!saved||linkat(s.job,part.c_str(),s.job,body.c_str(),0)!=0) { outcome="read_error";detail="export_finalize_failed"; }
    else if(unlinkat(s.job,part.c_str(),0)!=0) { outcome="read_error";detail="export_part_unlink_failed"; }
  }
  if(!line(s.results,"{\"keyId\":"+std::to_string(r->item.id)+",\"lookupUrl\":"+quote(r->item.url)+
    ",\"status\":"+quote(outcome)+",\"reason\":"+quote(detail)+",\"reportedObjectBytes\":"+std::to_string(r->expected)+
    ",\"exportedBytes\":"+std::to_string(r->bytes)+",\"startedAt\":"+quote(r->startedAt)+",\"completedAt\":"+quote(utc())+",\"file\":"+quote(outcome=="exported"?body:(saved?part:""))+
    ",\"cacheReadOnly\":true,\"formalQualificationClaimed\":false}"))s.disabled=true;
  if(r->reader) { TSIOBufferReaderFree(r->reader);r->reader=nullptr; }
  if(r->buffer) { TSIOBufferDestroy(r->buffer);r->buffer=nullptr; }
  if(r->key) { TSCacheKeyDestroy(r->key);r->key=nullptr; }
  // Read/continuation retained (max 8*128) so late cancellation callbacks cannot dereference freed state.
  s.active=nullptr;
}
bool drain(Read *r) {
  while(TSIOBufferReaderAvail(r->reader)>0) {
    TSIOBufferBlock block=TSIOBufferReaderStart(r->reader);int64_t n=0;
    const char *p=TSIOBufferBlockReadStart(block,r->reader,&n);n=std::min<int64_t>(n,65536);
    if(!p||n<=0||r->bytes+uint64_t(n)>uint64_t(r->expected)||s.total+uint64_t(n)>TotalLimit)return false;
    if(!write_all(r->fd,p,size_t(n)))return false;
    r->bytes+=n;s.total+=n;TSIOBufferReaderConsume(r->reader,n);
  }
  return true;
}
void start_key(const Key &k) {
  auto *r=new Read;r->item=k;r->started=std::chrono::steady_clock::now();r->startedAt=utc();s.active=r;
  r->cont=TSContCreate(cache_event,s.mutex);TSContDataSet(r->cont,r);
  r->key=TSCacheKeyCreate();TSMBuffer b=TSMBufferCreate();TSMLoc u=TS_NULL_MLOC;
  const char *begin=k.url.data();const char *end=begin+k.url.size();
  bool ok=TSUrlCreate(b,&u)==TS_SUCCESS&&TSUrlParse(b,u,&begin,end)==TS_PARSE_DONE&&begin==end&&
    TSCacheKeyDigestFromUrlSet(r->key,u)==TS_SUCCESS&&TSCacheKeyDataTypeSet(r->key,TS_CACHE_DATA_TYPE_HTTP)==TS_SUCCESS;
  if(ok) { int n=0;const char *host=TSUrlHostGet(b,u,&n);ok=host&&n>0&&TSCacheKeyHostNameSet(r->key,host,n)==TS_SUCCESS; }
  if(u!=TS_NULL_MLOC)TSHandleMLocRelease(b,TS_NULL_MLOC,u);
  TSMBufferDestroy(b);
  if(!ok) { finish(r,"read_error","key_creation_failed");return; }
  r->action=TSCacheRead(r->cont,r->key);
}
void accept_request() {
  if(s.controls>=16||s.jobs>=RequestLimit)return;
  // Only a private runroot file triggers reads. No URL or output path is accepted from it.
  if(syscall(SYS_renameat2,s.directory,"request.ready",s.directory,"request.active",1)!=0)return;
  ++s.controls;int f=openat(s.directory,"request.active",O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);
  struct stat st{};std::string raw;bool ok=f>=0&&fstat(f,&st)==0&&S_ISREG(st.st_mode)&&st.st_uid==getuid()&&
    (st.st_mode&0777)==0600&&st.st_nlink==1&&st.st_size>0&&st.st_size<=8192;
  if(ok) { raw.resize(size_t(st.st_size));size_t n=0;while(n<raw.size()) { ssize_t x=read(f,&raw[n],raw.size()-n);if(x<=0){ok=false;break;}n+=x; } }
  if(f>=0)close(f);
  std::istringstream input(raw);std::string id,v;std::getline(input,id);
  ok=ok&&std::regex_match(id,std::regex("[A-Za-z0-9_-]{1,32}"));std::vector<Key> assigned;std::set<unsigned> seen;
  { std::lock_guard<std::mutex> lock(s.catalogMutex);
    while(ok&&std::getline(input,v)) {
      if(!std::regex_match(v,std::regex("[1-9][0-9]{0,2}"))){ok=false;break;}
      unsigned n=unsigned(std::stoul(v));
      if(n>s.keys.size()||!seen.insert(n).second||assigned.size()>=RequestKeys){ok=false;break;}
      assigned.push_back(s.keys[n-1]);
    }
  }
  ok=ok&&!assigned.empty();std::string name="request-"+id;
  if(ok)ok=mkdirat(s.directory,name.c_str(),0700)==0;
  if(ok) { s.job=openat(s.directory,name.c_str(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);ok=s.job>=0; }
  if(ok) { s.results=create(s.job,"results.jsonl");ok=s.results>=0; }
  if(ok) {
    renameat(s.directory,"request.active",s.job,"request.txt");++s.jobs;s.assigned=std::move(assigned);s.next=0;
    line(s.events,"{\"event\":\"request_accepted\",\"requestId\":"+quote(id)+",\"keys\":"+std::to_string(s.assigned.size())+"}");
  } else {
    if(s.results>=0){close(s.results);s.results=-1;}if(s.job>=0){close(s.job);s.job=-1;}
    std::string rejected="rejected-"+std::to_string(s.controls)+".txt";
    renameat(s.directory,"request.active",s.directory,rejected.c_str());
    line(s.events,"{\"event\":\"request_rejected\",\"retainedFile\":"+quote(rejected)+"}");
  }
}
int work(TSCont,TSEvent,void *) {
  s.scheduled=false;flush_catalog();
  if(!s.cacheReady&&!s.disabled) {
    int ready=0,httpReady=0;
    if(TSCacheReady(&ready)==TS_SUCCESS&&ready&&
       TSCacheDataTypeReady(TS_CACHE_DATA_TYPE_HTTP,&httpReady)==TS_SUCCESS&&httpReady) {
      int fd=create(s.directory,"cache-ready.json.part");
      std::string row="{\"atsPid\":"+std::to_string(getpid())+",\"observedAt\":"+quote(utc())+
        ",\"cacheReady\":true,\"httpCacheReady\":true,\"nativeApi\":\"TSCacheReady+TSCacheDataTypeReady\"}";
      bool saved=fd>=0&&line(fd,row)&&fsync(fd)==0;
      if(fd>=0&&close(fd)!=0)saved=false;
      if(saved) {
        saved=linkat(s.directory,"cache-ready.json.part",s.directory,"cache-ready.json",0)==0;
        if(saved&&unlinkat(s.directory,"cache-ready.json.part",0)!=0)saved=false;
      }
      if(saved)s.cacheReady=true;else s.disabled=true;
    }
  }
  while(!s.pending.empty()) {
    Event e=s.pending.front();s.pending.pop_front();Read *r=e.read;if(r->done)continue;
    if(e.event==TS_EVENT_CACHE_OPEN_READ) {
      r->opening=false;r->vc=static_cast<TSVConn>(e.data);r->expected=TSVConnCacheObjectSizeGet(r->vc);
      if(r->expected<0||uint64_t(r->expected)>ObjectLimit||uint64_t(r->expected)>TotalLimit-s.total) { finish(r,"read_error","size_limit_or_unknown_size");continue; }
      r->fd=create(s.job,"key-"+std::to_string(r->item.id)+".body.part");
      if(r->fd<0) { finish(r,"read_error","exclusive_file_create_failed");continue; }
      // Reduce the observer's real allocation granularity. CacheVC may append
      // a whole Doc before testing this watermark; neither value is a hard cap.
      r->buffer=TSIOBufferSizedCreate(TS_IOBUFFER_SIZE_INDEX_8K);TSIOBufferWaterMarkSet(r->buffer,16384);
      r->reader=TSIOBufferReaderAlloc(r->buffer);r->vio=TSVConnRead(r->vc,r->cont,r->buffer,r->expected+1);
      if(!r->vio)finish(r,"read_error","cache_read_vio_unavailable");
    } else if(e.event==TS_EVENT_CACHE_OPEN_READ_FAILED) {
      r->opening=false;finish(r,"open_read_failed","ATS_event_error_"+std::to_string(reinterpret_cast<intptr_t>(e.data)));
    } else if(e.event==TS_EVENT_VCONN_READ_READY||e.event==TS_EVENT_VCONN_READ_COMPLETE||e.event==TS_EVENT_VCONN_EOS) {
      if(!drain(r)) { finish(r,"read_error","write_or_byte_limit_failed");continue; }
      if(e.event==TS_EVENT_VCONN_EOS||e.event==TS_EVENT_VCONN_READ_COMPLETE)
        finish(r,r->bytes==uint64_t(r->expected)?"exported":"read_error",r->bytes==uint64_t(r->expected)?(e.event==TS_EVENT_VCONN_EOS?"cache_body_eos":"cache_body_read_complete"):"terminal_byte_count_mismatch");
      else TSVIOReenable(r->vio);
    } else { finish(r,"read_error","ATS_read_event_"+std::to_string(e.event)); }
  }
  if(s.active&&std::chrono::steady_clock::now()-s.active->started>std::chrono::seconds(15))finish(s.active,"read_error","read_deadline");
  if(s.disabled)return 0;
  if(s.job<0)accept_request();
  while(s.job>=0&&!s.active) {
    if(s.next<s.assigned.size())start_key(s.assigned[s.next++]);
    else { fsync(s.results);close(s.results);close(s.job);s.results=s.job=-1;line(s.events,"{\"event\":\"request_finished\",\"qualificationClaimed\":false}");break; }
  }
  return 0;
}
int tick(TSCont,TSEvent,void *) { schedule();return 0; }
int ready(TSCont,TSEvent,void *) {
  TSCont timer=TSContCreate(tick,s.mutex);TSContScheduleEveryOnPool(timer,250,TS_THREAD_POOL_TASK);return 0;
}
} // namespace

void TSPluginInit(int argc,const char *argv[]) {
  TSPluginRegistrationInfo info={const_cast<char *>("lab_cache_export"),const_cast<char *>("Guize local lab"),const_cast<char *>("local-only")};
  if(argc!=2||TSPluginRegister(&info)!=TS_SUCCESS||TSTrafficServerVersionGetMajor()!=9||TSTrafficServerVersionGetMinor()!=2||TSTrafficServerVersionGetPatch()!=3) { TSError("lab_cache_export: explicit ATS9.2.3 private runroot required");return; }
  char resolved[4096];struct stat st{};
  if(!realpath(argv[1],resolved)||std::string(resolved)!=argv[1])return;
  int root=open(resolved,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
  if(root<0)return;
  std::string instance="cache-export-"+std::to_string(getpid());
  if(fstat(root,&st)!=0||st.st_uid!=getuid()||(st.st_mode&0777)!=0700||mkdirat(root,instance.c_str(),0700)!=0){close(root);return;}
  s.directory=openat(root,instance.c_str(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);close(root);
  if(s.directory<0)return;
  s.lookups=create(s.directory,"lookups.jsonl");s.lookupEvents=create(s.directory,"lookup-events.jsonl");s.events=create(s.directory,"events.jsonl");
  if(s.lookups<0||s.lookupEvents<0||s.events<0)return;
  s.mutex=TSMutexCreate();s.work=TSContCreate(work,s.mutex);
  TSHttpHookAdd(TS_HTTP_CACHE_LOOKUP_COMPLETE_HOOK,TSContCreate(capture,nullptr));
  TSLifecycleHookAdd(TS_LIFECYCLE_TASK_THREADS_READY_HOOK,TSContCreate(ready,s.mutex));
}
