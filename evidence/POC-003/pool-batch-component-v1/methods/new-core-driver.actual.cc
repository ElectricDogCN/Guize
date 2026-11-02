// Real new-core ABI check: one requested item, actual page rounding, retained charge and reuse.
#include "tscore/ink_config.h"
#include "tscore/ink_queue.h"
#include "live_buffer_accounting.h"
#include <cassert>
#include <cstring>
#include <dlfcn.h>
#include <iostream>
#include <string>
#include <vector>
int main(int argc,char **argv) {
  assert(argc==2);void *core=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);assert(core);
  auto init=reinterpret_cast<void(*)(InkFreeList**,const char*,uint32_t,uint32_t,uint32_t)>(dlsym(core,"ink_freelist_init"));
  auto alloc=reinterpret_cast<void*(*)(InkFreeList*)>(dlsym(core,"ink_freelist_new"));
  auto give=reinterpret_cast<void(*)(InkFreeList*,void*)>(dlsym(core,"ink_freelist_free"));
  auto acquire=reinterpret_cast<void(*)(unsigned,uint64_t)>(dlsym(core,"GuizeAtsLiveBufferAcquire"));
  auto release=reinterpret_cast<void(*)(unsigned,uint64_t)>(dlsym(core,"GuizeAtsLiveBufferRelease"));
  auto snapshot=reinterpret_cast<guize_live_buffer::Snapshot(*)(unsigned)>(dlsym(core,"GuizeAtsLiveBufferSnapshot"));
  assert(init&&alloc&&give&&acquire&&release&&snapshot);
  auto healthy=[](const guize_live_buffer::Snapshot &s){assert(s.abiVersion==1&&s.generation==0&&s.violations==0&&s.uncoveredExternalEvents==0);};
  healthy(snapshot(0));assert(snapshot(0).currentBytes==0);
  uint64_t retained=0;std::string cases="[";
  const unsigned sizes[]={128,8192,65536};const char *names[]={"ioBufAllocator[0]","ioBufAllocator[6]","ioBufAllocator[9]"};
  for(unsigned c=0;c<3;++c) {
    InkFreeList *pool=nullptr;init(&pool,names[c],sizes[c],1,sizes[c]<8192?sizes[c]:8192);
    assert(pool&&pool->type_size==sizes[c]&&pool->chunk_size>=1);
    const auto chunk=pool->chunk_size;std::vector<void*> held;
    for(unsigned i=0;i<5;++i) {
      acquire(guize_live_buffer::IO_BUFFER,pool->type_size);void *payload=alloc(pool);assert(payload);
      std::memset(payload,7,pool->type_size);held.push_back(payload);
    }
    assert(pool->allocated==((5+chunk-1)/chunk)*chunk&&pool->used==5);
    const uint64_t backing=uint64_t(pool->allocated)*pool->type_size;retained+=backing;
    const auto held_state=snapshot(0);healthy(held_state);assert(held_state.currentBytes==retained+5*pool->type_size);
    for(void *payload:held){give(pool,payload);release(guize_live_buffer::IO_BUFFER,pool->type_size);}
    assert(pool->used==0);const auto returned=snapshot(0);healthy(returned);assert(returned.currentBytes==retained);
    const auto allocated=pool->allocated;
    for(unsigned i=0;i<128;++i) {
      acquire(guize_live_buffer::IO_BUFFER,pool->type_size);void *payload=alloc(pool);assert(payload);
      std::memset(payload,9,pool->type_size);give(pool,payload);release(guize_live_buffer::IO_BUFFER,pool->type_size);
    }
    const auto reused=snapshot(0);healthy(reused);
    assert(pool->allocated==allocated&&pool->used==0&&reused.currentBytes==retained&&reused.peakBytes==returned.peakBytes);
    if(c)cases+=",";
    cases+="{\"typeBytes\":"+std::to_string(pool->type_size)+",\"requestedChunkItems\":1,\"actualChunkItems\":"+std::to_string(chunk)+",\"allocatedItems\":"+std::to_string(allocated)+",\"backingBytes\":"+std::to_string(backing)+",\"returnedCurrentBytes\":"+std::to_string(returned.currentBytes)+"}";
  }
  cases+="]";
  const auto end=snapshot(0);healthy(end);assert(end.currentBytes==retained);
  std::cout<<"READY\n"<<std::flush;std::string line;std::getline(std::cin,line);assert(line=="GO");
  std::cout<<"{\"actualCases\":"<<cases<<",\"retainedBytes\":"<<retained<<",\"peakBytes\":"<<end.peakBytes<<",\"abiHealthy\":true,\"media8MiBAccepted\":false}\n"<<std::flush;
}
