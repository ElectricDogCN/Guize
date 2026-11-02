// Ordinary native boundary tests; no ATS service or media qualification.
#include "live_pool_capacity.h"
#include <cassert>
#include <iostream>
using namespace guize_live_buffer;
int main() {
  uint64_t capacity=0;
  assert(is_iobuffer_pool("ioBufAllocator[0]"));
  assert(is_iobuffer_pool("ioBufAllocator[15]"));
  assert(!is_iobuffer_pool(nullptr)&&!is_iobuffer_pool("ioBufAllocator")&&!is_iobuffer_pool("other[0]"));
  assert(checked_pool_growth_capacity(128,8192,1048576,4096,false,0,capacity)&&capacity==1048576);
  assert(checked_pool_growth_capacity(1,7000,7000,4096,false,0,capacity)&&capacity==8192);
  assert(checked_pool_growth_capacity(1,7000,7000,4096,true,2097152,capacity)&&capacity==2097152);
  assert(checked_pool_growth_capacity(1,7000,7000,2097152,true,4096,capacity)&&capacity==2097152);
  assert(!checked_pool_growth_capacity(0,1,0,4096,false,0,capacity));
  assert(!checked_pool_growth_capacity(1,0,0,4096,false,0,capacity));
  assert(!checked_pool_growth_capacity(65536,65536,0,4096,false,0,capacity));
  const auto limit=std::numeric_limits<uint64_t>::max();
  assert(!checked_pool_growth_capacity(limit,2,limit,4096,false,0,capacity));
  assert(!checked_pool_growth_capacity(1,limit,limit,4096,false,0,capacity));
  assert(!checked_pool_growth_capacity(1,7000,7000,0,false,0,capacity));
  assert(!checked_pool_growth_capacity(1,7000,7000,3000,false,0,capacity));
  assert(!checked_pool_growth_capacity(1,7000,7000,4096,true,0,capacity));
  assert(!checked_pool_growth_capacity(1,7000,7000,4096,true,3000,capacity));
  std::cout<<"pool prefix, page/huge rounding, original32 truncation and uint64 overflow boundaries PASS\n";
}
