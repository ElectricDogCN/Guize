// Tests the exact ledger header copied into the instrumented core, not ATS itself.
#include "live_buffer_accounting.h"
#include <atomic>
#include <cassert>
#include <iostream>
#include <thread>
#include <vector>
using namespace guize_live_buffer;

int main() {
  {
    Ledger ledger;
    assert(ledger.acquire(AGGREGATION,4ULL<<20));
    assert(ledger.acquire(IO_BUFFER,2ULL<<20));
    auto start=ledger.snapshot(true);
    assert(start.currentBytes==(6ULL<<20)&&start.peakBytes==start.currentBytes&&start.generation==1);
    assert(ledger.release(IO_BUFFER,2ULL<<20));
    auto end=ledger.snapshot();
    assert(end.currentBytes==(4ULL<<20)&&end.peakBytes==(6ULL<<20));
    assert(end.liveByKind[IO_BUFFER]==0&&end.violations==0);
    std::cout<<"baseline retained; released payload excluded from current, retained in peak\n";
  }
  {
    Ledger ledger;
    constexpr unsigned workers=16;
    std::atomic<unsigned> entered{0};std::atomic<bool> leave{false};
    std::vector<std::thread> threads;
    assert(ledger.acquire(AGGREGATION,4ULL<<20));
    for(unsigned i=0;i<workers;++i)threads.emplace_back([&]{
      assert(ledger.acquire(IO_BUFFER,1ULL<<20));++entered;
      while(!leave.load())std::this_thread::yield();
      assert(ledger.release(IO_BUFFER,1ULL<<20));
    });
    while(entered.load()!=workers)std::this_thread::yield();
    auto together=ledger.snapshot();
    assert(together.currentBytes==(20ULL<<20)&&together.peakBytes==(20ULL<<20));
    assert(together.liveByKind[IO_BUFFER]==workers);
    leave=true;for(auto &thread:threads)thread.join();
    auto end=ledger.snapshot();
    assert(end.currentBytes==(4ULL<<20)&&end.peakBytes==(20ULL<<20)&&end.violations==0);
    assert(end.acquisitions[IO_BUFFER]==workers&&end.releases[IO_BUFFER]==workers);
    std::cout<<"16 concurrent allocations: exact simultaneous peak, balanced releases\n";
  }
  {
    Ledger ledger;assert(ledger.acquire(EXTERNAL,8192));
    auto first=ledger.snapshot(true);assert(first.uncoveredExternalEvents==1);
    assert(ledger.release(EXTERNAL,8192));
    assert(ledger.snapshot().uncoveredExternalEvents==1);
    auto next=ledger.snapshot(true);assert(next.uncoveredExternalEvents==0&&next.currentBytes==0);
    std::cout<<"unknown external payload prevents coverage within its observation window\n";
  }
  {
    Ledger ledger;assert(!ledger.release(IO_BUFFER,1));
    assert(ledger.snapshot(true).violations==1);
    assert(ledger.acquire(IO_BUFFER,4));assert(!ledger.release(IO_BUFFER,5));
    auto after=ledger.snapshot();assert(after.violations==2&&after.currentBytes==4);
    std::cout<<"underflow invalidates observations and cannot be cleared by reset\n";
  }
  {
    Ledger ledger;assert(ledger.acquire(AGGREGATION,4));
    assert(!ledger.acquire(IO_BUFFER,std::numeric_limits<uint64_t>::max()));
    auto after=ledger.snapshot();assert(after.violations==1&&after.currentBytes==4);
    std::cout<<"overflow invalidates observations without wrapping accounting\n";
  }
  {
    Ledger ledger;
    assert(ledger.acquire(AGGREGATION,4ULL<<20));
    assert(ledger.acquire(RECOVERY,8ULL<<20));
    assert(ledger.snapshot().peakBytes==(12ULL<<20));
    assert(ledger.release(RECOVERY,8ULL<<20));
    auto steady=ledger.snapshot(true);
    assert(steady.currentBytes==(4ULL<<20)&&steady.peakBytes==(4ULL<<20));
    assert(steady.currentByKind[RECOVERY]==0&&steady.violations==0);
    std::cout<<"released recovery excluded after ready reset; aggregation baseline retained\n";
  }
  std::cout<<"6 ledger scenarios passed; no ATS experiment executed\n";
}
