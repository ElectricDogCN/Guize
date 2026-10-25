// Actual shared ATS backing pool under simultaneous ordinary-user allocations.
#include "tscore/ink_config.h"
#include "tscore/ink_queue.h"
#include "live_buffer_accounting.h"
#include <atomic>
#include <cassert>
#include <cstring>
#include <dlfcn.h>
#include <iostream>
#include <thread>
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
  std::atomic<unsigned> entered{0};std::atomic<bool> leave{false};std::vector<std::thread> threads;
  for(unsigned i=0;i<16;++i)threads.emplace_back([&] {
    acquire(guize_live_buffer::IO_BUFFER,8192);void *payload=alloc(pool);assert(payload);
    std::memset(payload,7,8192);++entered;
    while(!leave.load())std::this_thread::yield();
    give(pool,payload);release(guize_live_buffer::IO_BUFFER,8192);
  });
  while(entered.load()!=16)std::this_thread::yield();
  const uint64_t backing=uint64_t(pool->allocated)*pool->type_size;
  const auto held=snapshot(0);assert(pool->used==16&&pool->allocated>=16);
  std::cout<<"READY\n"<<std::flush;std::string line;std::getline(std::cin,line);assert(line=="GO");
  leave=true;for(auto &thread:threads)thread.join();const auto returned=snapshot(0);
  assert(pool->used==0);
  const auto allocated=pool->allocated;
  for(unsigned i=0;i<128;++i) {
    acquire(guize_live_buffer::IO_BUFFER,8192);void *payload=alloc(pool);assert(payload);
    give(pool,payload);release(guize_live_buffer::IO_BUFFER,8192);
  }
  const auto reused=snapshot(0);assert(pool->allocated==allocated&&pool->used==0);
  std::cout<<"{\"backingBytes\":"<<backing<<",\"heldCurrent\":"<<held.currentBytes
    <<",\"peakBytes\":"<<held.peakBytes<<",\"returnedCurrent\":"<<returned.currentBytes
    <<",\"reusedCurrent\":"<<reused.currentBytes<<",\"allocatedItems\":"<<pool->allocated
    <<",\"usedItems\":"<<pool->used<<"}\n"<<std::flush;
  return returned.currentBytes==backing&&reused.currentBytes==backing&&held.currentBytes==backing+16*8192?0:2;
}
