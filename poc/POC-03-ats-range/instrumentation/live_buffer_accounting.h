// Task-owned diagnostic accounting. No storage allocation or ATS behavior policy.
#pragma once
#include <array>
#include <cstdint>
#include <limits>
#include <mutex>

namespace guize_live_buffer {
enum Kind : unsigned { IO_BUFFER=0, AGGREGATION=1, EXTERNAL=2, RECOVERY=3, KINDS=4 };
struct Snapshot {
  uint64_t abiVersion=1, generation=0, currentBytes=0, peakBytes=0;
  uint64_t violations=0, uncoveredExternalEvents=0;
  std::array<uint64_t,KINDS> currentByKind{}, liveByKind{}, acquisitions{}, releases{};
};

class Ledger {
  std::mutex mutex_;
  Snapshot state_;
  using PeakWriter=bool (*)(void *,const Snapshot &);
  PeakWriter writer_;
  void *writerContext_;
public:
  explicit Ledger(PeakWriter writer=nullptr,void *context=nullptr):writer_(writer),writerContext_(context) {}
  // Call before the actual allocation. A failure makes all later snapshots unhealthy.
  bool acquire(unsigned kind,uint64_t bytes) {
    std::lock_guard<std::mutex> lock(mutex_);
    if(kind>=KINDS||bytes==0||bytes>std::numeric_limits<uint64_t>::max()-state_.currentBytes) {
      ++state_.violations;return false;
    }
    state_.currentBytes+=bytes;state_.currentByKind[kind]+=bytes;
    ++state_.liveByKind[kind];++state_.acquisitions[kind];
    if(kind==EXTERNAL)++state_.uncoveredExternalEvents;
    if(state_.currentBytes>state_.peakBytes) {
      state_.peakBytes=state_.currentBytes;
      // The caller may allocate only after this synchronous publication succeeds.
      // Keep the same ledger lock across the counter update and publication.
      if(writer_&&!writer_(writerContext_,state_)) { ++state_.violations;return false; }
    }
    return true;
  }
  // Call after release is complete. Interleaving can conservatively overcount.
  bool release(unsigned kind,uint64_t bytes) {
    std::lock_guard<std::mutex> lock(mutex_);
    if(kind>=KINDS||bytes==0||bytes>state_.currentByKind[kind]||state_.liveByKind[kind]==0) {
      ++state_.violations;return false;
    }
    state_.currentBytes-=bytes;state_.currentByKind[kind]-=bytes;
    --state_.liveByKind[kind];++state_.releases[kind];return true;
  }
  Snapshot snapshot(bool resetWindow=false) {
    std::lock_guard<std::mutex> lock(mutex_);
    if(resetWindow) {
      // A journal-bound ledger is process-lifetime; old peaks cannot be erased.
      if(writer_) { ++state_.violations;return state_; }
      ++state_.generation;state_.peakBytes=state_.currentBytes;
      // Unknown external storage may outlive its wrapper. Keep this risk
      // process-lifetime sticky; wrapper release cannot prove owner release.
    }
    return state_;
  }
};
} // namespace guize_live_buffer

// Defined once in the patched core library, not separately per translation unit.
extern "C" void GuizeAtsLiveBufferAcquire(unsigned kind,uint64_t bytes);
extern "C" void GuizeAtsLiveBufferRelease(unsigned kind,uint64_t bytes);
extern "C" guize_live_buffer::Snapshot GuizeAtsLiveBufferSnapshot(unsigned resetWindow);
