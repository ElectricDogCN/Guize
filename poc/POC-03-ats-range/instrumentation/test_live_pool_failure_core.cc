// Real core pool preallocation failures and ordinary-user hugepage fallback.
#include "tscore/ink_config.h"
#include "tscore/ink_queue.h"
#include "live_buffer_accounting.h"
#include <cassert>
#include <cerrno>
#include <csignal>
#include <cstring>
#include <dlfcn.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <sys/resource.h>
#include <unistd.h>
int main(int argc,char **argv) {
  assert(argc==4);void *core=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);assert(core);
  const std::string scenario=argv[2];const std::filesystem::path directory=argv[3];
  auto init=reinterpret_cast<void(*)(InkFreeList**,const char*,uint32_t,uint32_t,uint32_t)>(dlsym(core,"ink_freelist_init"));
  auto alloc=reinterpret_cast<void*(*)(InkFreeList*)>(dlsym(core,"ink_freelist_new"));
  auto give=reinterpret_cast<void(*)(InkFreeList*,void*)>(dlsym(core,"ink_freelist_free"));
  auto acquire=reinterpret_cast<void(*)(unsigned,uint64_t)>(dlsym(core,"GuizeAtsLiveBufferAcquire"));
  auto release=reinterpret_cast<void(*)(unsigned,uint64_t)>(dlsym(core,"GuizeAtsLiveBufferRelease"));
  auto snapshot=reinterpret_cast<guize_live_buffer::Snapshot(*)(unsigned)>(dlsym(core,"GuizeAtsLiveBufferSnapshot"));
  assert(init&&alloc&&give&&acquire&&release&&snapshot);assert(snapshot(0).currentBytes==0);
  uint64_t huge_bytes=0;int huge_errno=0;
  if(scenario=="huge-fallback") {
    auto huge_init=reinterpret_cast<void(*)(int)>(dlsym(core,"_Z17ats_hugepage_initi"));
    auto huge_enabled=reinterpret_cast<bool(*)()>(dlsym(core,"_Z20ats_hugepage_enabledv"));
    auto huge_size=reinterpret_cast<size_t(*)()>(dlsym(core,"_Z17ats_hugepage_sizev"));
    auto huge_alloc=reinterpret_cast<void*(*)(size_t)>(dlsym(core,"_Z18ats_alloc_hugepagem"));
    assert(huge_init&&huge_enabled&&huge_size&&huge_alloc);huge_init(1);
    assert(huge_enabled());huge_bytes=huge_size();assert(huge_bytes&&huge_bytes<=16777216);
    errno=0;void *probe=huge_alloc(huge_bytes);huge_errno=errno;
    // This profile is deliberately the host's unavailable-hugepage fallback.
    // Success is a different unmeasured profile and must not become this PASS.
    assert(!probe&&huge_errno);
  }
  InkFreeList *pool=nullptr;init(&pool,"ioBufAllocator[2]",8192,4,4096);
  assert(pool&&pool->allocated==0);
  std::cout<<"READY\n"<<std::flush;std::string line;std::getline(std::cin,line);assert(line=="GO");
  if(scenario=="invalid-product") {
    // Deliberately corrupt only this private test pool's allocation dimensions.
    pool->chunk_size=65536;pool->type_size=65536;
  } else if(scenario=="write-failure") {
    std::filesystem::path journal;
    for(const auto &entry:std::filesystem::directory_iterator(directory))
      if(entry.path().filename().string().rfind("peak-",0)==0)journal=entry.path();
    assert(!journal.empty());auto size=std::filesystem::file_size(journal);
    signal(SIGXFSZ,SIG_IGN);rlimit limit{rlim_t(size+37),rlim_t(size+37)};
    assert(setrlimit(RLIMIT_FSIZE,&limit)==0);
  } else assert(scenario=="huge-fallback");
  if(scenario=="huge-fallback")acquire(guize_live_buffer::IO_BUFFER,8192);
  void *payload=alloc(pool);assert(payload);
  if(scenario!="huge-fallback") {
    std::ofstream(directory/"allocation-returned.marker")<<"unexpected return after rejected growth\n";
    return 2;
  }
  std::memset(payload,7,8192);const auto held=snapshot(0);
  std::ifstream maps("/proc/self/smaps");std::string record;bool target=false;uint64_t page_bytes=0;
  std::ofstream mapping(directory/"target-smaps.raw");
  const auto address=reinterpret_cast<uintptr_t>(payload);
  while(std::getline(maps,record)) {
    unsigned long long begin=0,end=0;
    if(std::sscanf(record.c_str(),"%llx-%llx",&begin,&end)==2)target=begin<=address&&address<end;
    if(target) {
      mapping<<record<<'\n';
      if(record.rfind("KernelPageSize:",0)==0) {
        std::istringstream values(record.substr(15));values>>page_bytes;page_bytes*=1024;
      }
    }
  }
  mapping.close();assert(page_bytes&&page_bytes<huge_bytes);
  const uint64_t backing=uint64_t(pool->allocated)*pool->type_size;
  give(pool,payload);release(guize_live_buffer::IO_BUFFER,8192);const auto returned=snapshot(0);
  assert(backing==huge_bytes&&returned.currentBytes>=backing&&held.currentBytes>=backing+8192);
  std::cout<<"{\"hugeEnabled\":true,\"hugeBytes\":"<<huge_bytes<<",\"directHugeAttemptErrno\":"<<huge_errno
    <<",\"actualPoolKernelPageBytes\":"<<page_bytes<<",\"backingBytes\":"<<backing
    <<",\"heldCurrent\":"<<held.currentBytes<<",\"returnedCurrent\":"<<returned.currentBytes<<"}\n"<<std::flush;
  return 0;
}
