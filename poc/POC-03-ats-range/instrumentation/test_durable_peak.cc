// Ordinary-user native component regression. No ATS, HTTP or POC workload.
#include "live_buffer_accounting.h"
#include "live_peak_journal.h"
#include <atomic>
#include <cassert>
#include <csignal>
#include <fstream>
#include <filesystem>
#include <iostream>
#include <sys/resource.h>
#include <sys/wait.h>
#include <thread>
#include <vector>
using namespace guize_live_buffer;

void marker(const char *directory) {
  std::ofstream(std::string(directory)+"/payload-after-hook.marker")<<"actual allocation hook returned\n";
}
int main(int argc,char **argv) {
  assert(argc==3);const std::string scenario=argv[1];const char *directory=argv[2];
  DurableAccounting accounting(directory);
  if(scenario=="zero")return 0;
  if(scenario=="underflow") { accounting.release(IO_BUFFER,1);marker(directory);return 1; }
  if(scenario=="reset") { accounting.snapshot(1);marker(directory);return 1; }
  if(scenario=="external") {
    std::vector<unsigned char> outside(65536,42);
    accounting.acquire(EXTERNAL,outside.size());marker(directory);return 1;
  }
  if(scenario=="write-failure") {
    // Limit only this process's writes to a prefix of its next real journal row.
    // The initial row fits; the next write is genuinely short then returns EFBIG.
    const auto pid=std::to_string(getpid());
    std::string file;
    for(const auto &entry:std::filesystem::directory_iterator(directory))
      if(entry.path().filename().string().rfind("peak-"+pid+"-",0)==0)file=entry.path();
    assert(!file.empty());const auto bytes=std::filesystem::file_size(file);
    signal(SIGXFSZ,SIG_IGN);rlimit limit{rlim_t(bytes+37),rlim_t(bytes+37)};
    assert(setrlimit(RLIMIT_FSIZE,&limit)==0);
    accounting.acquire(IO_BUFFER,4194304);marker(directory);return 1;
  }
  if(scenario=="quota") {
    for(unsigned i=0;i<4096;++i)accounting.acquire(IO_BUFFER,1);
    marker(directory);return 1;
  }
  if(scenario=="fork") {
    accounting.acquire(IO_BUFFER,64);const auto child=fork();assert(child>=0);
    if(child==0) { accounting.acquire(IO_BUFFER,1);marker(directory);_exit(1); }
    int status=0;assert(waitpid(child,&status,0)==child&&WIFEXITED(status)&&WEXITSTATUS(status)==70);
    accounting.release(IO_BUFFER,64);
    std::cout<<"fork rejected before inherited ledger/descriptor use; parent remains valid\n";return 0;
  }
  if(scenario=="exec") {
    accounting.acquire(IO_BUFFER,64);execl(argv[0],argv[0],"exec-replay",directory,nullptr);return 1;
  }
  if(scenario=="exec-replay")return 1; // Constructor must have rejected O_EXCL epoch reuse.
  if(scenario=="capture") {
    accounting.acquire(IO_BUFFER,1048576);std::vector<unsigned char> payload(1048576,7);
    std::cout<<"READY\n"<<std::flush;
    std::string command;std::getline(std::cin,command);assert(command=="RELEASE");
    std::vector<unsigned char>().swap(payload);accounting.release(IO_BUFFER,1048576);
    assert(accounting.snapshot().currentBytes==0);return 0;
  }
  if(scenario=="normal") {
    accounting.acquire(AGGREGATION,4194304);
    // The peak row must exist before actual target payload creation.
    bool persisted=false;
    for(const auto &entry:std::filesystem::directory_iterator(directory)) {
      std::ifstream input(entry.path());std::string row;
      while(std::getline(input,row))persisted=persisted||row.find("\"peakBytes\":4194304")!=std::string::npos;
    }
    assert(persisted);std::vector<unsigned char> payload(4194304,3);marker(directory);
    accounting.acquire(RECOVERY,8388608);
    std::vector<unsigned char> recovery(8388608,4);std::vector<unsigned char>().swap(recovery);
    accounting.release(RECOVERY,8388608);const auto ready=accounting.snapshot();
    assert(ready.generation==0&&ready.currentBytes==4194304&&ready.peakBytes==12582912);
    std::vector<unsigned char>().swap(payload);accounting.release(AGGREGATION,4194304);
    assert(accounting.snapshot().peakBytes==12582912);
    std::cout<<"durable before payload; released early recovery peak retained without reset\n";return 0;
  }
  assert(scenario=="concurrent");
  std::atomic<unsigned> entered{0};std::atomic<bool> leave{false};std::vector<std::thread> threads;
  for(unsigned i=0;i<16;++i)threads.emplace_back([&]{
    accounting.acquire(IO_BUFFER,1048576);std::vector<unsigned char> payload(1048576,1);++entered;
    while(!leave.load())std::this_thread::yield();
    std::vector<unsigned char>().swap(payload);accounting.release(IO_BUFFER,1048576);
  });
  while(entered.load()!=16)std::this_thread::yield();
  assert(accounting.snapshot().peakBytes==16777216);leave=true;
  for(auto &thread:threads)thread.join();
  assert(accounting.snapshot().currentBytes==0&&accounting.snapshot().peakBytes==16777216);
  std::cout<<"16 concurrent actual payloads; peak remains after release\n";
}
