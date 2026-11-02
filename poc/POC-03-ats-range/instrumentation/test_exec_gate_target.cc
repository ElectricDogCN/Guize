// Ordinary native core canary; no ATS server, network or media input.
#include "live_buffer_accounting.h"
#include <cassert>
#include <csignal>
#include <dlfcn.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sys/resource.h>
#include <unistd.h>
#include <vector>
int main(int argc,char **argv) {
  assert(argc==4);const std::string mode=argv[2];const std::filesystem::path marker=argv[3];
  {std::ofstream output(marker);output<<getpid()<<'\n';}
  if(mode=="no-journal")return 0;
  void *core=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);assert(core);
  auto acquire=reinterpret_cast<void(*)(unsigned,uint64_t)>(dlsym(core,"GuizeAtsLiveBufferAcquire"));
  auto release=reinterpret_cast<void(*)(unsigned,uint64_t)>(dlsym(core,"GuizeAtsLiveBufferRelease"));
  auto snapshot=reinterpret_cast<guize_live_buffer::Snapshot(*)(unsigned)>(dlsym(core,"GuizeAtsLiveBufferSnapshot"));
  assert(acquire&&release&&snapshot);assert(snapshot(0).currentBytes==0);
  if(mode=="partial-journal") {
    std::filesystem::path journal;
    for(const auto &entry:std::filesystem::directory_iterator(marker.parent_path()))
      if(entry.path().filename().string().rfind("peak-",0)==0)journal=entry.path();
    assert(!journal.empty());const auto bytes=std::filesystem::file_size(journal);
    signal(SIGXFSZ,SIG_IGN);rlimit limit{rlim_t(bytes+37),rlim_t(bytes+37)};
    assert(setrlimit(RLIMIT_FSIZE,&limit)==0);
  }
  acquire(guize_live_buffer::IO_BUFFER,1048576);std::vector<unsigned char> body(1048576,7);
  acquire(guize_live_buffer::RECOVERY,2097152);std::vector<unsigned char> early(2097152,9);
  std::vector<unsigned char>().swap(early);release(guize_live_buffer::RECOVERY,2097152);
  auto state=snapshot(0);assert(state.currentBytes==1048576&&state.peakBytes==3145728);
  if(mode=="held") {
    std::cout<<"TARGET_READY\n"<<std::flush;std::string line;std::getline(std::cin,line);assert(line=="EXIT");
  }
  std::vector<unsigned char>().swap(body);release(guize_live_buffer::IO_BUFFER,1048576);
  if(mode=="late-failure") {release(guize_live_buffer::IO_BUFFER,1);return 2;}
  assert(mode=="held"||mode=="fast");return 0;
}
