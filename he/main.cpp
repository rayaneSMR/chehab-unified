#include <chrono>
    #include <cstddef>
    #include <fstream>
    #include <iostream>
    #include <ostream> 
    #include <atomic>
    #include <thread>
    #if defined(_WIN32)
    #include <windows.h>
    #include <psapi.h>
    #elif defined(__APPLE__)
    #include <mach/mach.h>
    #elif defined(__linux__) || defined(__linux) || defined(linux) || defined(__unix__)
    #include <unistd.h>
    #include <sys/resource.h>
    #include <cstdio>
    #endif
    #include "_gen_he_fhe.hpp"
    #include "utils.hpp"

    using namespace std;
    using namespace seal;

    inline size_t getCurrentRSS() {
    #if defined(_WIN32)
        PROCESS_MEMORY_COUNTERS pmc;
        if (GetProcessMemoryInfo(GetCurrentProcess(), &pmc, sizeof(pmc))) {
            return static_cast<size_t>(pmc.WorkingSetSize);
        }
        return 0;
    #elif defined(__APPLE__)
        struct mach_task_basic_info info;
        mach_msg_type_number_t count = MACH_TASK_BASIC_INFO_COUNT;
        if (task_info(mach_task_self(), MACH_TASK_BASIC_INFO, (task_info_t)&info, &count) == KERN_SUCCESS) {
            return static_cast<size_t>(info.resident_size);
        }
        return 0;
    #elif defined(__linux__) || defined(__linux) || defined(linux) || defined(__unix__)
        long rss = 0;
        FILE* fp = fopen("/proc/self/statm", "r");
        if (fp) {
            long pages = 0, resident = 0;
            if (fscanf(fp, "%ld %ld", &pages, &resident) == 2) {
                long page_size = sysconf(_SC_PAGESIZE);
                if (page_size <= 0) page_size = 4096;
                rss = resident * page_size;
            }
            fclose(fp);
        }
        if (rss == 0) {
            struct rusage usage;
            if (getrusage(RUSAGE_SELF, &usage) == 0) {
                rss = usage.ru_maxrss * 1024;
            }
        }
        return static_cast<size_t>(rss);
    #else
        return 0;
    #endif
    }

    struct RamMemSampler {
        std::atomic<bool> running{false};
        std::atomic<size_t> peak_used{0};
        std::thread th;

        void start() {
            peak_used = 0;
            running = true;
            th = std::thread([this]() {
                while (running.load()) {
                    size_t used = getCurrentRSS();
                    size_t prev = peak_used.load();
                    while (used > prev &&
                           !peak_used.compare_exchange_weak(prev, used)) {}
                    std::this_thread::sleep_for(std::chrono::microseconds(100));
                }
            });
        }

        void stop() {
            running = false;
            if (th.joinable()) th.join();
        }
    };

    void print_bool_arg(bool arg, const string &name, ostream &os)
    {
      os << (arg ? name : "no" + name); 
    }

    int main(int argc, char **argv)
    {
      RamMemSampler sampler;
      sampler.start();

      bool opt = true;
      if (argc > 1)
        opt = stoi(argv[1]);

      print_bool_arg(opt, "opt", clog);
      clog << '\n';

      string app_name = "fhe";
      ifstream is("../" + app_name + "_io_example_adapted.txt");
      if (!is)
        throw invalid_argument("failed to open io example file");
        EncryptionParameters params(scheme_type::bfv); 
  size_t n =16384 ;
  params.set_poly_modulus_degree(n);
  params.set_plain_modulus(PlainModulus::Batching(n, 20)); 
params.set_coeff_modulus(CoeffModulus::BFVDefault(16384));
  SEALContext context(params, true, sec_level_type::tc128);

      ClearArgsInfo clear_inputs, clear_outputs;
      size_t func_slot_count;
      BatchEncoder batch_encoder(context);
      KeyGenerator keygen(context);
      const SecretKey &secret_key = keygen.secret_key();
      PublicKey public_key;
      keygen.create_public_key(public_key);
      RelinKeys relin_keys;
      keygen.create_relin_keys(relin_keys);
      GaloisKeys galois_keys; 
      chrono::high_resolution_clock::time_point keys_time;
      chrono::duration<double, milli> keys_elapsed;
      keys_time = chrono::high_resolution_clock::now();      
      //keygen.create_galois_keys(galois_keys);
      keygen.create_galois_keys(get_rotation_steps_fhe(), galois_keys);
      keys_elapsed = chrono::high_resolution_clock::now() - keys_time;

      size_t galois_keys_total_size = galois_keys.save_size();
      cout << "rotation_keys_size_(MB): " << galois_keys_total_size / (1024.0 * 1024.0) << endl;
      Encryptor encryptor(context, public_key);
      Evaluator evaluator(context);
      Decryptor decryptor(context, secret_key);
      EncryptedArgs encrypted_inputs;
      EncodedArgs encoded_inputs;
      
      chrono::high_resolution_clock::time_point t;
      chrono::duration<double, milli> elapsed;
      t = chrono::high_resolution_clock::now();

      parse_inputs_outputs_file(is, params.plain_modulus().value(), clear_inputs, clear_outputs, func_slot_count);
      prepare_he_inputs(batch_encoder, encryptor, clear_inputs, encrypted_inputs, encoded_inputs);
      EncryptedArgs encrypted_outputs;
      EncodedArgs encoded_outputs;

      fhe(
        encrypted_inputs, encoded_inputs, encrypted_outputs, encoded_outputs, batch_encoder, encryptor, evaluator,
        relin_keys, galois_keys);

      elapsed = chrono::high_resolution_clock::now() - t;

      ClearArgsInfo obtained_clear_outputs;
      get_clear_outputs(
        batch_encoder, decryptor, encrypted_outputs, encoded_outputs, func_slot_count, obtained_clear_outputs);
      print_encrypted_outputs_info(context, decryptor, encrypted_outputs, clog);
      cout <<"circuit_execution_time_(ms): "<<elapsed.count() <<"\n"<<std::flush;
      cout <<"galois_keys_generation_time_(ms): "<<keys_elapsed.count() <<"\n"<<std::flush;
      double total_time = elapsed.count() + keys_elapsed.count();
      cout <<"total_execution_time_(ms): "<<total_time <<"\n"<<std::flush;
      print_variables_values(obtained_clear_outputs, std::cout);

      sampler.stop();
      cout << "peak_ram_memory_(MB): "
           << sampler.peak_used.load() / (1024.0 * 1024.0) << "\n" << std::flush;
    }
    