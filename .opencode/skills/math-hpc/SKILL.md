---
name: math-hpc
description: High-Performance Computing: CUDA optimization, SIMD/vectorization, numerical methods (ODE/PDE solvers, FFT, matrix decompositions), parallel computing (MPI, OpenMP, NCCL), Julia for HPC, and roofline model analysis
license: MIT
compatibility: opencode
metadata:
  audience: systems-engineers
  domain: math-hpc
  paradigm: parallel
  integrates_with: [math-ml, systems-embedded, systems-ebpf, backend-python, backend-go]
---

## Math HPC (High-Performance Computing) Skill

### CUDA Optimization
- **Kernel design**: Thread hierarchy (grid > block > thread); thread block size = multiple of 32 (warp); occupancy calculator
- **Memory hierarchy**: Registers (fastest) > Shared memory > L1/L2 cache > Global memory (slowest)
- **Shared memory**: __shared__ for block-level cache; bank conflict avoidance (padding); sync via __syncthreads()
- **Coalesced access**: Adjacent threads access adjacent addresses; avoid strided access
- **Warp-level**: Warp shuffle (__shfl_xor_sync) for intra-warp communication; no shared memory needed
- **Streams**: Concurrent kernel execution; cudaStream_t; overlap compute with data transfer
- **Tensor Cores**: MMA operations; FP16/BF16/INT8/FP8; wmma or mma.sync PTX; cuBLAS/cuDNN for automatic

### SIMD & Vectorization
- **x86**: SSE (128-bit), AVX2 (256-bit), AVX-512 (512-bit, Intel only); _mm256_* intrinsics; compiler auto-vectorization (-O3 -mavx2)
- **ARM**: NEON (128-bit), SVE (scalable, up to 2048-bit); arm_neon.h intrinsics
- **RISC-V**: V extension (RVV); scalable vector length; vsetvl, vadd.vv
- **Rust portable SIMD**: std::simd (nightly); portable without intrinsics
- **Loop optimizations**: Loop unrolling, loop fusion, loop interchange, loop tiling (cache blocking)

### Numerical Methods
- **ODE solvers**: Runge-Kutta 4/5 (explicit), DOPRI5 (adaptive), implicit methods for stiff systems (Backward Euler, BDF)
- **PDE solvers**: Finite Difference (structured grids), Finite Element (unstructured, weak form), Finite Volume (conservation laws), Spectral (Fourier/Chebyshev, high accuracy)
- **FFT**: Cooley-Tukey (O(N log N)); cuFFT for GPU; real-to-complex saves 2x; zero-padding for interpolation
- **Linear algebra**: LAPACK (CPU), cuSOLVER/MAGMA (GPU); iterative: Conjugate Gradient (SPD), GMRES (non-symmetric)
- **Matrix decompositions**: LU (general solve), Cholesky (SPD, 2x faster), QR (least squares), SVD (pseudoinverse, PCA), Eigendecomposition

### Parallel Computing
- **MPI**: Point-to-point (MPI_Send/Recv), collectives (MPI_Allreduce, MPI_Bcast, MPI_Gather); non-blocking for overlap; cartesian topologies for grid problems
- **OpenMP**: #pragma omp parallel for; reduction, critical, atomic; schedule(dynamic) for load imbalance
- **NCCL**: GPU-aware collectives; AllReduce (Ring/Tree), AllGather, ReduceScatter; NVLink/NVSwitch for intra-node
- **Julia parallel**: Threads.@threads; Distributed.jl for multi-node; GPUArrays.jl for GPU; KernelAbstractions.jl for portable kernels

### Roofline Model
- **Compute bound**: Arithmetic intensity (FLOPs/byte) above ridge point; optimize for compute (vectorization, FMA)
- **Memory bound**: Below ridge point; optimize for bandwidth (cache blocking, prefetching, data layout)
- **Ceilings**: Peak FLOPs (theoretical), peak bandwidth (STREAM benchmark); in-practice ceilings (90% theoretical)

### Julia for HPC
- **Multiple dispatch**: Type-based function selection at runtime; JIT compiled to native code via LLVM
- **Type stability**: All variables in a function must have concrete types; @code_warntype to check
- **GPU**: CUDA.jl (NVIDIA), AMDGPU.jl, Metal.jl (Apple); kernel! function with thread indexing
- **SIMD**: LoopVectorization.jl for auto-vectorization; SIMD.jl for explicit
- **Distributed**: Distributed.jl + MPI.jl for multi-node

### Common Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| False sharing in parallel loops | Adjacent array elements on same cache line cause invalidation ping-pong across cores | Pad data structures to cache line boundaries (64 bytes on x86) |
| NUMA-unaware memory allocation | Memory allocated on remote NUMA node has 2-3x latency penalty | Use `numactl --cpunodebind` + `--membind`; first-touch allocation policy |
| Strided memory access on GPU | Non-coalesced access wastes memory bandwidth; 4-8x throughput reduction | Ensure adjacent threads access adjacent memory addresses |
| Not using unified memory on GPU | Manual `cudaMalloc` + `cudaMemcpy` increases code complexity and bug surface | Use `cudaMallocManaged` with prefetch hints for Pascal+ GPUs |
| Too-small thread blocks on GPU | Underutilizes SMs; occupancy < 25% on modern GPUs | Thread block size = multiple of 32 (warp size); minimum 128 threads |
| `MPI_Send` without matching `MPI_Recv` | Deadlock; message not consumed; buffer exhaustion | Use `MPI_Sendrecv` for symmetrical exchanges; `MPI_Isend` + `MPI_Irecv` for overlap |
| OpenMP `schedule(static)` for unbalanced workload | Some threads finish early while others are still processing | Use `schedule(dynamic)` or `schedule(guided)` for imbalanced workloads |
| Premature optimization without roofline | Optimizing compute when memory-bound; or vice versa | Always compute arithmetic intensity first; compare against roofline model |

### Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---|---|---|---|
| CUDA kernel launches but returns wrong results | Race condition; thread synchronization missing | `cuda-memcheck --tool racecheck` | Add `__syncthreads()` barriers; check shared memory access patterns |
| `cudaErrorMemoryAllocation` | GPU memory exhausted | `nvidia-smi` shows memory usage near max | Reduce batch size; use gradient checkpointing; enable memory pooling |
| MPI program hangs | One rank stuck in wait; mismatched collective | `mpirun -np N xterm -e gdb ./program` | Verify all ranks call same collectives; check conditional MPI paths |
| OpenMP scaling plateaus after 4 threads | Memory bandwidth saturated; NUMA effects | `likwid-perfctr` for memory bandwidth; roofline analysis | Optimize memory layout; use NUMA-aware initialization |
| NANs in numerical output | Division by zero; sqrt of negative; overflow | Check FP exception flags; `feenableexcept(FE_DIVBYZERO \| FE_INVALID)` | Add assertions on intermediate values; use `-ffpe-trap=invalid,zero,overflow` |
| FFT results show spectral leakage | Non-periodic signal; wrong window function | Compare with known reference; check window type | Apply Hann/Hamming window before FFT; zero-pad to power of 2 |

### Implementation Checklist

- [ ] Algorithm selection justified with complexity analysis (Big-O)
- [ ] Roofline model computed for target hardware (peak FLOPs, peak bandwidth)
- [ ] Arithmetic intensity computed for the kernel/hot loop
- [ ] Memory access pattern optimized for coalescing (GPU) or cache line (CPU)
- [ ] Data layout chosen for access pattern (AoS vs SoA)
- [ ] SIMD/vectorization enabled (compiler flags `-march=native -O3` or explicit intrinsics)
- [ ] CUDA kernel thread block size tuned for occupancy (≥ 128, multiple of 32)
- [ ] MPI communication/computation overlap enabled (non-blocking operations)
- [ ] NUMA pinning configured for multi-socket systems
- [ ] Profiling run: Nsight Systems (GPU), VTune/`perf` (CPU), `likwid` (microarchitecture)
- [ ] Numerical stability verified (condition numbers, error bounds, convergence criteria)
- [ ] Test with multiple problem sizes to verify scaling behavior
- [ ] Unit tests for numerical correctness with known-answer benchmarks
- [ ] Performance regression tests in CI pipeline
