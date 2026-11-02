// Exact ATS ioBufAllocator backing-pool growth bound; no allocation or release.
#pragma once
#include <cstdint>
#include <cstring>
#include <limits>

namespace guize_live_buffer {
inline bool is_iobuffer_pool(const char *name) {
  // IOBuffer.cc constructs ioBufAllocator[%d]. A superset only overcounts.
  return name && std::strncmp(name,"ioBufAllocator[",15)==0;
}
inline bool checked_pool_growth_capacity(uint64_t count,uint64_t type_bytes,uint64_t actual_size,
                                        uint64_t page_bytes,bool huge_enabled,uint64_t huge_bytes,
                                        uint64_t &capacity) {
  const auto limit=std::numeric_limits<uint64_t>::max();
  if(!count||!type_bytes||count>limit/type_bytes)return false;
  const auto exact=count*type_bytes;
  // ATS's original multiplication must not already have truncated at uint32.
  if(actual_size!=exact)return false;
  auto rounded=[&](uint64_t alignment,uint64_t &value) {
    if(!alignment||(alignment&(alignment-1))||exact>limit-(alignment-1))return false;
    value=(exact+alignment-1)&~(alignment-1);return value!=0;
  };
  uint64_t ordinary=0,huge=0;
  if(!rounded(page_bytes,ordinary)||(huge_enabled&&!rounded(huge_bytes,huge)))return false;
  capacity=ordinary>huge?ordinary:huge;
  return true;
}
} // namespace guize_live_buffer
