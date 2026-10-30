// Link with --no-as-needed: this target never calls a Guize accounting API.
// Actual DT_NEEDED/maps must identify the loaded core, not merely this source.
#include <cassert>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <unistd.h>
int main(int argc,char **argv) {
  assert(argc==3);
  const auto entered=std::chrono::steady_clock::now().time_since_epoch();
  const char *directory=getenv("GUIZE_POC003_PEAK_JOURNAL_DIR");assert(directory&&*directory);
  const std::filesystem::path output=argv[2];
  unsigned journals=0;uintmax_t bytes=0;
  for(const auto &entry:std::filesystem::directory_iterator(directory)) {
    const std::string prefix="peak-"+std::to_string(getpid())+"-";
    if(entry.path().filename().string().rfind(prefix,0)==0) {
      ++journals;bytes+=std::filesystem::file_size(entry.path());
    }
  }
  {std::ifstream input("/proc/self/maps");std::ofstream maps(output.string()+".maps.raw");maps<<input.rdbuf();}
  {std::ofstream marker(output);marker<<"{\"pid\":"<<getpid()
    <<",\"mainEnteredMonotonicNs\":"<<std::chrono::duration_cast<std::chrono::nanoseconds>(entered).count()
    <<",\"journalFilesAtMain\":"<<journals<<",\"journalBytesAtMain\":"<<bytes
    <<",\"guizeApiCalled\":false}\n";}
  const bool expected=std::string(argv[1])=="journal";
  assert(expected||std::string(argv[1])=="no-journal");
  assert(journals==(expected?1u:0u));assert(!expected||bytes>0);
  std::cout<<"MAIN_COMPLETED_WITHOUT_GUIZE_API\n";return 0;
}
