// Bare CUDA program: measures what a CUDA process costs BEFORE any HEonGPU allocation
// (context + driver + one loaded kernel module + cuRAND/cuFFT-free). run_total_mem.py reports
// its device delta / host RSS; fit_gpu_full.py uses rows whose id starts with "ctx_probe".
// Build: nvcc -O2 -arch=sm_80 ctx_probe.cu -o ctx_probe
#include <cuda_runtime.h>
#include <cstdio>
#include <unistd.h>

__global__ void touch(int* p) { if (p) p[0] = 1; }

int main() {
    cudaFree(0);                       // force context creation
    int* d = nullptr;
    cudaMalloc(&d, 1 << 20);           // 1 MiB so an allocation path is exercised
    touch<<<1, 1>>>(d);                // forces module load
    cudaDeviceSynchronize();
    size_t f = 0, t = 0;
    cudaMemGetInfo(&f, &t);
    printf("CTX_PROBE used_MiB=%.1f total_MiB=%.1f\n", (t - f) / 1048576.0, t / 1048576.0);
    usleep(700000);                    // let the external poller see the plateau
    cudaFree(d);
    return 0;
}
