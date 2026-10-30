// Exercise actual ATS pool growth, return and reuse through the built core ABI.
#include "tscore/ink_config.h"
#include "tscore/ink_queue.h"
#include "live_buffer_accounting.h"
#include <cassert>
#include <cstring>
#include <dlfcn.h>
#include <iostream>
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
  assert(snapshot(0).currentBytes==0);
  InkFreeList *pool=nullptr;init(&pool,"ioBufAllocator[2]",8192,4,4096);
  assert(pool&&pool->type_size==8192&&pool->chunk_size==4);
  std::vector<void*> held;
  for(unsigned i=0;i<5;++i) {
    acquire(guize_live_buffer::IO_BUFFER,pool->type_size);
    void *payload=alloc(pool);assert(payload);std::memset(payload,7,pool->type_size);held.push_back(payload);
  }
  assert(pool->allocated==8&&pool->used==5);
  const uint64_t backing=uint64_t(pool->allocated)*pool->type_size;
  const auto held_state=snapshot(0);
  for(void *payload:held) {give(pool,payload);release(guize_live_buffer::IO_BUFFER,pool->type_size);}
  assert(pool->used==0&&pool->allocated==8);
  const auto returned=snapshot(0);
  // Repeated use of existing backing blocks must not charge a fresh grow.
  for(unsigned i=0;i<128;++i) {
    acquire(guize_live_buffer::IO_BUFFER,pool->type_size);void *payload=alloc(pool);assert(payload);
    std::memset(payload,9,pool->type_size);give(pool,payload);release(guize_live_buffer::IO_BUFFER,pool->type_size);
  }
  const auto reused=snapshot(0);assert(pool->allocated==8&&pool->used==0);
  assert(reused.currentBytes==returned.currentBytes&&reused.peakBytes==held_state.peakBytes);
  std::cout<<"READY\n"<<std::flush;std::string line;std::getline(std::cin,line);assert(line=="GO");
  std::cout<<"{\"backingBytes\":"<<backing<<",\"heldCurrent\":"<<held_state.currentBytes
    <<",\"peakBytes\":"<<held_state.peakBytes<<",\"returnedCurrent\":"<<returned.currentBytes
    <<",\"reusedCurrent\":"<<reused.currentBytes<<",\"allocatedItems\":"<<pool->allocated
    <<",\"usedItems\":"<<pool->used<<"}\n"<<std::flush;
  return returned.currentBytes>=backing&&held_state.currentBytes>=backing+5*8192?0:2;
}
