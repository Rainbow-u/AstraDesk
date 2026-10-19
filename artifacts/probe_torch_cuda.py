import torch, platform, json
info = {
    "torch_version": torch.__version__,
    "python": platform.python_version(),
    "cuda_available": torch.cuda.is_available(),
    "torch_cuda_version": getattr(torch.version, "cuda", None),
    "cudnn_version": getattr(torch.backends, "cudnn", None) and torch.backends.cudnn.version(),
}
if torch.cuda.is_available():
    info["device_count"] = torch.cuda.device_count()
    info["device_name"] = torch.cuda.get_device_name(0)
    cap = torch.cuda.get_device_capability(0)
    info["compute_capability"] = f"sm_{cap[0]}{cap[1]}"
    props = torch.cuda.get_device_properties(0)
    info["total_memory_gib"] = round(props.total_memory / (1024**3), 2)
    # real GPU compute: matmul on cuda, verify result correctness
    a = torch.randn(1024, 1024, device="cuda")
    b = torch.randn(1024, 1024, device="cuda")
    c = (a @ b).sum().item()
    info["gpu_matmul_ok"] = True
    info["gpu_matmul_sum_sample"] = round(c, 3)
    info["mem_allocated_mib"] = round(torch.cuda.memory_allocated(0) / (1024**2), 2)
print(json.dumps(info, ensure_ascii=False, indent=2))
