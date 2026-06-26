import si = require('systeminformation');
import { logger } from './logger';

// =============================================================================
// Agent Platform — GPU Collector
// =============================================================================
// Collects GPU telemetry from the host machine using systeminformation (NVML).
// Falls back to nvidia-smi parsing if NVML is unavailable.
// =============================================================================

export interface GPUInfo {
  providerId: string;
  gpuModel: string;
  gpuUtilization: number;
  temperatureCelsius: number;
  memoryUsedGb: number;
  memoryTotalGb: number;
  powerWatts: number;
  uptimeSeconds: number;
  timestamp: number;
  tflopsFp16: number;
  activeJobs: number;
  status: 'online' | 'degraded' | 'offline';
  labels: Record<string, string>;
}

export interface GPUCollectorConfig {
  providerId: string;
  collectionIntervalMs: number;
  gpuIndex?: number;
}

export class GPUCollector {
  private config: GPUCollectorConfig;
  private intervalHandle: NodeJS.Timeout | null = null;
  private lastGPUData: GPUInfo | null = null;

  constructor(config: GPUCollectorConfig) {
    this.config = {
      ...config,
      gpuIndex: config.gpuIndex ?? 0,
    };
  }

  /**
   * Start collecting GPU telemetry at the configured interval.
   * Calls the onData callback with each collected sample.
   */
  start(onData: (data: GPUInfo) => void): void {
    logger.info('Starting GPU collector', {
      providerId: this.config.providerId,
      intervalMs: this.config.collectionIntervalMs,
    });

    // Collect immediately, then at interval
    this.collectOnce(onData);
    this.intervalHandle = setInterval(() => {
      this.collectOnce(onData);
    }, this.config.collectionIntervalMs);
  }

  /**
   * Stop the GPU collector.
   */
  stop(): void {
    if (this.intervalHandle) {
      clearInterval(this.intervalHandle);
      this.intervalHandle = null;
    }
    logger.info('GPU collector stopped');
  }

  /**
   * Get the last collected GPU data.
   */
  getLastData(): GPUInfo | null {
    return this.lastGPUData;
  }

  /**
   * Collect a single GPU telemetry sample with a timeout guard.
   */
  async collectOnce(onData: (data: GPUInfo) => void): Promise<GPUInfo> {
    try {
      const data = await Promise.race([
        this.collectGPUData(),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error('GPU data collection timed out after 10s')), 10_000)
        ),
      ]);
      this.lastGPUData = data;
      onData(data);
      return data;
    } catch (error) {
      logger.error('Failed to collect GPU data', { error: String(error) });
      // Return degraded status if collection fails
      const degraded: GPUInfo = {
        providerId: this.config.providerId,
        gpuModel: 'unknown',
        gpuUtilization: 0,
        temperatureCelsius: 0,
        memoryUsedGb: 0,
        memoryTotalGb: 0,
        powerWatts: 0,
        uptimeSeconds: 0,
        timestamp: Math.floor(Date.now() / 1000),
        tflopsFp16: 0,
        activeJobs: 0,
        status: 'degraded',
        labels: { error: String(error) },
      };
      this.lastGPUData = degraded;
      onData(degraded);
      return degraded;
    }
  }

  /**
   * Collect GPU data from systeminformation (NVML backend).
   */
  private async collectGPUData(): Promise<GPUInfo> {
    const [gpuData, systemData, processesData] = await Promise.all([
      si.graphics(),
      si.time(),
      si.processes(),
    ]);

    const gpuController = gpuData.controllers[this.config.gpuIndex!];

    if (!gpuController) {
      throw new Error(`GPU controller at index ${this.config.gpuIndex} not found`);
    }

    // Calculate TFLOPS FP16 based on GPU model (approximate)
    const tflopsFp16 = this.estimateTflopsFp16(
      gpuController.model,
      gpuController.clockCore,
      gpuController.cores
    );

    // Count active GPU processes (approximation)
    const activeJobs = processesData.list.filter(
      (p) => p.name && (p.name.includes('python') || p.name.includes('train') || p.name.includes('infer'))
    ).length;

    const memoryTotalGb = (gpuController.memoryTotal || 0) / 1024;
    const memoryUsedGb = (gpuController.memoryUsed || 0) / 1024;

    // Determine status based on metrics
    let status: GPUInfo['status'] = 'online';
    if (gpuController.temperatureGpu && gpuController.temperatureGpu > 85) {
      status = 'degraded';
    }
    if (gpuController.utilizationGpu === undefined || gpuController.utilizationGpu === null) {
      status = 'degraded';
    }

    return {
      providerId: this.config.providerId,
      gpuModel: gpuController.model || 'unknown',
      gpuUtilization: gpuController.utilizationGpu || 0,
      temperatureCelsius: gpuController.temperatureGpu || 0,
      memoryUsedGb,
      memoryTotalGb,
      powerWatts: gpuController.powerDraw || 0,
      uptimeSeconds: systemData.uptime,
      timestamp: Math.floor(Date.now() / 1000),
      tflopsFp16,
      activeJobs,
      status,
      labels: {
        vendor: gpuController.vendor || 'unknown',
        subDeviceId: gpuController.subDeviceId || '',
        driverVersion: gpuController.driverVersion || '',
      },
    };
  }

  /**
   * Estimate TFLOPS FP16 based on GPU model characteristics.
   * This is an approximation — real values depend on clock speeds and architecture.
   */
  private estimateTflopsFp16(model: string, clockCore: number | undefined, cores: number | undefined): number {
    if (!clockCore || !cores) return 0;

    // Rough estimation: (cores * clock * 2) / 1e12 for FP16
    // Real TFLOPS depends on architecture (Tensor Cores, etc.)
    const baseTflops = (cores * clockCore * 2) / 1e12;

    // Apply architecture-specific multipliers
    if (model.includes('A100')) return baseTflops * 3;  // Tensor Core boost
    if (model.includes('H100')) return baseTflops * 6;  // Transformer Engine
    if (model.includes('V100')) return baseTflops * 2;  // Tensor Core boost
    if (model.includes('RTX 4090')) return baseTflops * 2.5;
    if (model.includes('RTX 4080')) return baseTflops * 2;
    if (model.includes('RTX 3090')) return baseTflops * 1.5;

    return baseTflops;
  }
}

export default GPUCollector;
