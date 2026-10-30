// Private diagnostic observer for the exact instrumented ATS build.
// No HTTP interface; snapshots retain the instrumented process-lifetime peak.
#include <ts/ts.h>
#include <ts/experimental.h>
#include "live_buffer_accounting.h"
#include <cerrno>
#include <cstdlib>
#include <dlfcn.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <ctime>
#include <fstream>
#include <sstream>
#include <string>

#ifndef GUIZE_LIVE_HEADER_SHA256
#error Exact ledger header identity must be supplied by the build helper
#endif
#ifndef GUIZE_LIVE_OBSERVER_SHA256
#error Exact observer source identity must be supplied by the build helper
#endif

namespace {
using SnapshotFunction=guize_live_buffer::Snapshot (*)(unsigned);
SnapshotFunction snapshot=nullptr;
int output=-1;
uint64_t startTicks=0, sequence=0;
bool started=false, stopped=false;
constexpr uint64_t RecordLimit=4096;
uint64_t monotonic_ns() {
  timespec now{};
  if(clock_gettime(CLOCK_MONOTONIC,&now)!=0)return 0;
  return uint64_t(now.tv_sec)*1000000000+uint64_t(now.tv_nsec);
}
bool append(const std::string &record) {
  if(record.size()>2000)return false;
  const auto bytes=record+'\n';size_t offset=0;
  while(offset<bytes.size()) {
    auto count=write(output,bytes.data()+offset,bytes.size()-offset);
    if(count<0&&errno==EINTR)continue;
    if(count<=0)return false;
    offset+=size_t(count);
  }
  return fsync(output)==0;
}
template<class Array>std::string array_json(const Array &values) {
  std::string result="[";
  for(size_t i=0;i<values.size();++i) {
    if(i)result+=',';
    result+=std::to_string(values[i]);
  }
  return result+']';
}
int observe(TSCont,TSEvent,void *) {
  if(stopped)return 0;
  int cacheReady=0,httpReady=0;
  if(TSCacheReady(&cacheReady)!=TS_SUCCESS||!cacheReady||
     TSCacheDataTypeReady(TS_CACHE_DATA_TYPE_HTTP,&httpReady)!=TS_SUCCESS||!httpReady) {
    if(started) { append("{\"error\":\"native_cache_readiness_lost\"}");stopped=true; }
    return 0;
  }
  if(sequence>=RecordLimit) {
    append("{\"error\":\"record_limit\"}");stopped=true;return 0;
  }
  const bool reset=false;
  const auto before=monotonic_ns();
  const auto value=snapshot(reset?1:0);
  const auto after=monotonic_ns();
  if(!before||after<before||value.abiVersion!=1||value.generation!=0) {
    append("{\"error\":\"clock_or_abi_or_generation\"}");stopped=true;return 0;
  }
  std::string row="{\"kind\":\"INSTRUMENTED_ATS_LIVE_MEDIA_CAPACITY\",\"atsPid\":"+std::to_string(getpid())+
    ",\"startTicks\":"+std::to_string(startTicks)+",\"sequence\":"+std::to_string(sequence)+
    ",\"snapshotBeforeMonotonicNs\":"+std::to_string(before)+",\"snapshotAfterMonotonicNs\":"+std::to_string(after)+
    ",\"reset\":false,\"accountingWindow\":\"process-lifetime\",\"cacheReady\":true,\"httpCacheReady\":true,\"abiVersion\":"+std::to_string(value.abiVersion)+
    ",\"generation\":"+std::to_string(value.generation)+",\"currentBytes\":"+std::to_string(value.currentBytes)+
    ",\"peakBytes\":"+std::to_string(value.peakBytes)+",\"violations\":"+std::to_string(value.violations)+
    ",\"uncoveredExternalEvents\":"+std::to_string(value.uncoveredExternalEvents)+
    ",\"currentByKind\":"+array_json(value.currentByKind)+",\"liveByKind\":"+array_json(value.liveByKind)+
    ",\"acquisitions\":"+array_json(value.acquisitions)+",\"releases\":"+array_json(value.releases)+
    ",\"ledgerHeaderSha256\":\"" GUIZE_LIVE_HEADER_SHA256 "\",\"observerSourceSha256\":\"" GUIZE_LIVE_OBSERVER_SHA256
    "\",\"baselineSubtracted\":false,\"experimentApprovedByObserver\":false}";
  if(!append(row))stopped=true;
  else { started=true;++sequence; }
  return 0;
}
int ready(TSCont,TSEvent,void *) {
  TSContScheduleEveryOnPool(TSContCreate(observe,TSMutexCreate()),250,TS_THREAD_POOL_TASK);
  return 0;
}
} // namespace

void TSPluginInit(int argc,const char *argv[]) {
  TSPluginRegistrationInfo info={const_cast<char *>("guize_live_buffer_observer"),const_cast<char *>("Guize local lab"),const_cast<char *>("local-only")};
  if(argc!=2||getuid()==0||TSPluginRegister(&info)!=TS_SUCCESS||
     TSTrafficServerVersionGetMajor()!=9||TSTrafficServerVersionGetMinor()!=2||TSTrafficServerVersionGetPatch()!=3)return;
  char resolved[4096];struct stat metadata{};
  if(!realpath(argv[1],resolved)||std::string(resolved)!=argv[1])return;
  int directory=open(resolved,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
  if(directory<0)return;
  if(fstat(directory,&metadata)!=0||metadata.st_uid!=getuid()||(metadata.st_mode&0777)!=0700){close(directory);return;}
  const auto name="live-buffer-"+std::to_string(getpid())+".jsonl";
  output=openat(directory,name.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);close(directory);
  if(output<0)return;
  std::ifstream statFile("/proc/self/stat");std::string statLine;std::getline(statFile,statLine);
  auto closeParen=statLine.rfind(')');
  if(closeParen==std::string::npos){append("{\"error\":\"process_identity\"}");return;}
  std::istringstream fields(statLine.substr(closeParen+1));std::string field;
  for(unsigned index=0;index<=19;++index) {
    if(!(fields>>field)){append("{\"error\":\"process_identity\"}");return;}
  }
  try { startTicks=std::stoull(field); } catch(...) { append("{\"error\":\"process_identity\"}");return; }
  dlerror();snapshot=reinterpret_cast<SnapshotFunction>(dlsym(RTLD_DEFAULT,"GuizeAtsLiveBufferSnapshot"));
  if(!snapshot||dlerror()){append("{\"error\":\"instrumented_core_api_missing\"}");return;}
  TSLifecycleHookAdd(TS_LIFECYCLE_TASK_THREADS_READY_HOOK,TSContCreate(ready,TSMutexCreate()));
}
