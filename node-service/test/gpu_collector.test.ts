// =============================================================================
// Agent Platform — GPU Collector Tests
// =============================================================================

// Mock systeminformation BEFORE importing the module under test
jest.mock('systeminformation', () => ({
  graphics: jest.fn().mockResolvedValue({
    controllers: [
      {
        model: 'NVIDIA A100 80GB',
        vendor: 'NVIDIA',
        clockCore: 1000,
        cores: 100,
        memoryTotal: 81920, // 80 GB in MB
        memoryUsed: 40960,  // 40 GB in MB
        temperatureGpu: 65,
        utilizationGpu: 75,
        powerDraw: 250,
        subDeviceId: '0x0000',
        driverVersion: '525.85.05',
      },
    ],
  }),
  time: jest.fn().mockResolvedValue({ uptime: 3600 }),
  processes: jest.fn().mockResolvedValue({
    list: [
      { name: 'python' },
      { name: 'train_model' },
      { name: 'chrome' },
      { name: 'inference_server' },
    ],
  }),
}));

import { GPUCollector, GPUInfo } from '../src/gpu_collector';

describe('GPUCollector', () => {
  let collector: GPUCollector;

  beforeEach(() => {
    collector = new GPUCollector({
      providerId: 'test-node-1',
      collectionIntervalMs: 5000,
      gpuIndex: 0,
    });
  });

  afterEach(() => {
    collector.stop();
  });

  // ===========================================================================
  // Constructor
  // ===========================================================================
  describe('constructor', () => {
    it('should initialize with default gpuIndex when not provided', () => {
      const c = new GPUCollector({
        providerId: 'test-node-2',
        collectionIntervalMs: 10000,
      });
      expect(c).toBeDefined();
      expect((c as any).config.gpuIndex).toBe(0);
      c.stop();
    });

    it('should initialize with custom gpuIndex', () => {
      const c = new GPUCollector({
        providerId: 'test-node-3',
        collectionIntervalMs: 10000,
        gpuIndex: 1,
      });
      expect(c).toBeDefined();
      expect((c as any).config.gpuIndex).toBe(1);
      c.stop();
    });

    it('should accept collectionIntervalMs of 0', () => {
      const c = new GPUCollector({
        providerId: 'test-node-4',
        collectionIntervalMs: 0,
      });
      expect(c).toBeDefined();
      c.stop();
    });

    it('should accept empty providerId without throwing', () => {
      const c = new GPUCollector({
        providerId: '',
        collectionIntervalMs: 5000,
      });
      expect(c).toBeDefined();
      c.stop();
    });

    it('should accept very large collectionIntervalMs', () => {
      const c = new GPUCollector({
        providerId: 'test-node-5',
        collectionIntervalMs: 86400000, // 1 day
      });
      expect(c).toBeDefined();
      c.stop();
    });
  });

  // ===========================================================================
  // collectOnce
  // ===========================================================================
  describe('collectOnce', () => {
    it('should return GPUInfo with correct providerId', async () => {
      const onData = jest.fn();
      const result = await collector.collectOnce(onData);

      expect(result.providerId).toBe('test-node-1');
      expect(result.timestamp).toBeGreaterThan(0);
      expect(['online', 'degraded', 'offline']).toContain(result.status);
    });

    it('should call onData callback with GPUInfo', async () => {
      const onData = jest.fn();
      await collector.collectOnce(onData);

      expect(onData).toHaveBeenCalledTimes(1);
      expect(onData).toHaveBeenCalledWith(
        expect.objectContaining({
          providerId: 'test-node-1',
        })
      );
    });

    it('should update lastGPUData after collection', async () => {
      const onData = jest.fn();
      expect(collector.getLastData()).toBeNull();

      await collector.collectOnce(onData);

      const lastData = collector.getLastData();
      expect(lastData).not.toBeNull();
      expect(lastData!.providerId).toBe('test-node-1');
    });

    it('should handle collection errors gracefully', async () => {
      const badCollector = new GPUCollector({
        providerId: 'bad-node',
        collectionIntervalMs: 5000,
        gpuIndex: 999, // Invalid index
      });

      const onData = jest.fn();
      const result = await badCollector.collectOnce(onData);

      expect(result.status).toBe('degraded');
      expect(result.gpuModel).toBe('unknown');
      expect(onData).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'degraded' })
      );

      badCollector.stop();
    });

    it('should return timestamp close to current time', async () => {
      const onData = jest.fn();
      const before = Math.floor(Date.now() / 1000);
      const result = await collector.collectOnce(onData);
      const after = Math.floor(Date.now() / 1000);

      expect(result.timestamp).toBeGreaterThanOrEqual(before);
      expect(result.timestamp).toBeLessThanOrEqual(after);
    });

    it('should return labels with expected keys', async () => {
      const onData = jest.fn();
      const result = await collector.collectOnce(onData);

      expect(result.labels).toBeDefined();
      expect(result.labels).toHaveProperty('vendor');
      expect(result.labels).toHaveProperty('subDeviceId');
      expect(result.labels).toHaveProperty('driverVersion');
    });

    it('should return numeric memory values', async () => {
      const onData = jest.fn();
      const result = await collector.collectOnce(onData);

      expect(typeof result.memoryUsedGb).toBe('number');
      expect(typeof result.memoryTotalGb).toBe('number');
      expect(result.memoryUsedGb).toBeGreaterThanOrEqual(0);
      expect(result.memoryTotalGb).toBeGreaterThanOrEqual(0);
    });

    it('should return activeJobs as a non-negative number', async () => {
      const onData = jest.fn();
      const result = await collector.collectOnce(onData);

      expect(typeof result.activeJobs).toBe('number');
      expect(result.activeJobs).toBeGreaterThanOrEqual(0);
    });

    it('should update lastGPUData even on error', async () => {
      const badCollector = new GPUCollector({
        providerId: 'bad-node',
        collectionIntervalMs: 5000,
        gpuIndex: 999,
      });

      const onData = jest.fn();
      await badCollector.collectOnce(onData);

      const lastData = badCollector.getLastData();
      expect(lastData).not.toBeNull();
      expect(lastData!.status).toBe('degraded');

      badCollector.stop();
    });

    it('should work with an empty onData callback', async () => {
      const result = await collector.collectOnce(() => {});
      expect(result).toBeDefined();
      expect(result.providerId).toBe('test-node-1');
    });

    it('should return correct GPU model from systeminformation', async () => {
      const onData = jest.fn();
      const result = await collector.collectOnce(onData);

      expect(result.gpuModel).toBe('NVIDIA A100 80GB');
    });

    it('should calculate memory values correctly (MB to GB)', async () => {
      const onData = jest.fn();
      const result = await collector.collectOnce(onData);

      // 81920 MB = 80 GB, 40960 MB = 40 GB
      expect(result.memoryTotalGb).toBe(80);
      expect(result.memoryUsedGb).toBe(40);
    });

    it('should count active GPU-related processes', async () => {
      const onData = jest.fn();
      const result = await collector.collectOnce(onData);

      // python, train_model, inference_server = 3 active jobs
      expect(result.activeJobs).toBe(3);
    });
  });

  // ===========================================================================
  // start / stop (with fake timers)
  // ===========================================================================
  describe('start/stop', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('should start collecting at interval', () => {
      const collectSpy = jest.spyOn(collector as any, 'collectOnce');

      const onData = jest.fn();
      collector.start(onData);

      // Should have been called immediately on start
      expect(collectSpy).toHaveBeenCalledTimes(1);

      // Advance past the interval to trigger another collection
      jest.advanceTimersByTime(5000);
      expect(collectSpy).toHaveBeenCalledTimes(2);

      collectSpy.mockRestore();
    });

    it('should stop collecting', () => {
      const onData = jest.fn();
      collector.start(onData);
      collector.stop();

      const callCount = onData.mock.calls.length;
      jest.advanceTimersByTime(10000);
      expect(onData.mock.calls.length).toBe(callCount);
    });

    it('should not throw when stop is called before start', () => {
      expect(() => collector.stop()).not.toThrow();
    });

    it('should be safe to call stop multiple times', () => {
      collector.start(jest.fn());
      expect(() => {
        collector.stop();
        collector.stop();
        collector.stop();
      }).not.toThrow();
    });

    it('should collect immediately on start, not only after interval', () => {
      const collectSpy = jest.spyOn(collector as any, 'collectOnce');

      collector.start(jest.fn());

      // collectOnce should have been called immediately
      expect(collectSpy).toHaveBeenCalledTimes(1);

      collectSpy.mockRestore();
    });

    it('should not create multiple intervals when start is called multiple times', () => {
      const onData = jest.fn();
      collector.start(onData);
      collector.start(onData);
      collector.start(onData);

      // Advance time - should only have been called once per interval
      jest.advanceTimersByTime(5000);

      // 3 immediate calls (one per start) + 1 interval call
      expect(onData.mock.calls.length).toBeLessThanOrEqual(4);
    });

    it('should respect custom collection interval', () => {
      const customCollector = new GPUCollector({
        providerId: 'custom-interval',
        collectionIntervalMs: 1000,
      });

      // Spy on collectOnce to verify it's called without awaiting the promise
      const collectSpy = jest.spyOn(customCollector as any, 'collectOnce');

      const onData = jest.fn();
      customCollector.start(onData);

      // Should collect immediately
      expect(collectSpy).toHaveBeenCalledTimes(1);

      // Advance 1 second - should collect again
      jest.advanceTimersByTime(1000);
      expect(collectSpy).toHaveBeenCalledTimes(2);

      // Advance another 500ms - should NOT collect yet
      jest.advanceTimersByTime(500);
      expect(collectSpy).toHaveBeenCalledTimes(2);

      customCollector.stop();
      collectSpy.mockRestore();
    });
  });

  // ===========================================================================
  // Status detection
  // ===========================================================================
  describe('status detection', () => {
    it('should return status as one of the valid values', async () => {
      const onData = jest.fn();
      const result = await collector.collectOnce(onData);

      expect(['online', 'degraded', 'offline']).toContain(result.status);
    });

    it('should return degraded status on collection error', async () => {
      const badCollector = new GPUCollector({
        providerId: 'bad-node',
        collectionIntervalMs: 5000,
        gpuIndex: 999,
      });

      const onData = jest.fn();
      const result = await badCollector.collectOnce(onData);

      expect(result.status).toBe('degraded');
      badCollector.stop();
    });

    it('should have status field as a non-empty string', async () => {
      const onData = jest.fn();
      const result = await collector.collectOnce(onData);

      expect(typeof result.status).toBe('string');
      expect(result.status.length).toBeGreaterThan(0);
    });
  });

  // ===========================================================================
  // estimateTflopsFp16
  // ===========================================================================
  describe('estimateTflopsFp16', () => {
    const estimate = (GPUCollector.prototype as any).estimateTflopsFp16;

    it('should return 0 for missing clock or cores', () => {
      expect(estimate('A100', undefined, 100)).toBe(0);
      expect(estimate('A100', 1000, undefined)).toBe(0);
      expect(estimate('A100', undefined, undefined)).toBe(0);
    });

    it('should return 0 when clock is 0', () => {
      expect(estimate('A100', 0, 100)).toBe(0);
    });

    it('should return 0 when cores is 0', () => {
      expect(estimate('A100', 1000, 0)).toBe(0);
    });

    it('should return 0 when both clock and cores are 0', () => {
      expect(estimate('A100', 0, 0)).toBe(0);
    });

    it('should apply A100 multiplier', () => {
      const base = (100 * 1000 * 2) / 1e12;
      expect(estimate('NVIDIA A100 80GB', 1000, 100)).toBeCloseTo(base * 3, 10);
    });

    it('should apply H100 multiplier', () => {
      const base = (100 * 1000 * 2) / 1e12;
      expect(estimate('NVIDIA H100 80GB', 1000, 100)).toBeCloseTo(base * 6, 10);
    });

    it('should apply V100 multiplier', () => {
      const base = (100 * 1000 * 2) / 1e12;
      expect(estimate('NVIDIA V100 32GB', 1000, 100)).toBeCloseTo(base * 2, 10);
    });

    it('should apply RTX 4090 multiplier', () => {
      const base = (100 * 1000 * 2) / 1e12;
      expect(estimate('NVIDIA GeForce RTX 4090', 1000, 100)).toBeCloseTo(base * 2.5, 10);
    });

    it('should apply RTX 4080 multiplier', () => {
      const base = (100 * 1000 * 2) / 1e12;
      expect(estimate('NVIDIA GeForce RTX 4080', 1000, 100)).toBeCloseTo(base * 2, 10);
    });

    it('should apply RTX 3090 multiplier', () => {
      const base = (100 * 1000 * 2) / 1e12;
      expect(estimate('NVIDIA GeForce RTX 3090', 1000, 100)).toBeCloseTo(base * 1.5, 10);
    });

    it('should return base TFLOPS for unknown models', () => {
      const base = (100 * 1000 * 2) / 1e12;
      expect(estimate('Unknown GPU Model', 1000, 100)).toBeCloseTo(base, 10);
    });

    it('should handle very large clock and core values without overflow', () => {
      const result = estimate('Unknown GPU Model', 100000, 100000);
      expect(typeof result).toBe('number');
      expect(isFinite(result)).toBe(true);
      expect(result).toBeGreaterThan(0);
    });

    it('should handle model names with different casing', () => {
      const base = (100 * 1000 * 2) / 1e12;
      // The method uses model.includes('A100') which is case-sensitive
      // So lowercase 'nvidia a100 80gb' should NOT match and return base
      expect(estimate('nvidia a100 80gb', 1000, 100)).toBeCloseTo(base, 10);
    });
  });

  // ===========================================================================
  // GPUInfo interface validation
  // ===========================================================================
  describe('GPUInfo interface', () => {
    it('should have all required fields defined', async () => {
      const onData = jest.fn();
      const result = await collector.collectOnce(onData);

      const requiredFields: (keyof GPUInfo)[] = [
        'providerId',
        'gpuModel',
        'gpuUtilization',
        'temperatureCelsius',
        'memoryUsedGb',
        'memoryTotalGb',
        'powerWatts',
        'uptimeSeconds',
        'timestamp',
        'tflopsFp16',
        'activeJobs',
        'status',
        'labels',
      ];

      for (const field of requiredFields) {
        expect(result).toHaveProperty(field);
      }
    });

    it('should have numeric fields as finite numbers', async () => {
      const onData = jest.fn();
      const result = await collector.collectOnce(onData);

      const numericFields: (keyof GPUInfo)[] = [
        'gpuUtilization',
        'temperatureCelsius',
        'memoryUsedGb',
        'memoryTotalGb',
        'powerWatts',
        'uptimeSeconds',
        'timestamp',
        'tflopsFp16',
        'activeJobs',
      ];

      for (const field of numericFields) {
        expect(typeof result[field]).toBe('number');
        expect(Number.isFinite(result[field] as number)).toBe(true);
      }
    });

    it('should have status as one of the valid enum values', async () => {
      const onData = jest.fn();
      const result = await collector.collectOnce(onData);

      expect(['online', 'degraded', 'offline']).toContain(result.status);
    });
  });

  // ===========================================================================
  // Edge cases
  // ===========================================================================
  describe('edge cases', () => {
    it('should handle negative GPU index by returning degraded', async () => {
      const negativeCollector = new GPUCollector({
        providerId: 'negative-index',
        collectionIntervalMs: 5000,
        gpuIndex: -1,
      });

      const onData = jest.fn();
      const result = await negativeCollector.collectOnce(onData);

      expect(result.status).toBe('degraded');
      negativeCollector.stop();
    });

    it('should allow multiple independent collectors', async () => {
      const collector1 = new GPUCollector({
        providerId: 'multi-1',
        collectionIntervalMs: 5000,
        gpuIndex: 0,
      });

      const collector2 = new GPUCollector({
        providerId: 'multi-2',
        collectionIntervalMs: 5000,
        gpuIndex: 0,
      });

      const onData1 = jest.fn();
      const onData2 = jest.fn();

      const result1 = await collector1.collectOnce(onData1);
      const result2 = await collector2.collectOnce(onData2);

      expect(result1.providerId).toBe('multi-1');
      expect(result2.providerId).toBe('multi-2');

      collector1.stop();
      collector2.stop();
    });

    it('should propagate error from onData callback', async () => {
      const throwingCallback = jest.fn().mockImplementation(() => {
        throw new Error('callback error');
      });

      await expect(collector.collectOnce(throwingCallback)).rejects.toThrow('callback error');
    });

    it('should handle gpuIndex as string number', () => {
      const c = new GPUCollector({
        providerId: 'string-index',
        collectionIntervalMs: 5000,
        gpuIndex: '1' as any,
      });
      expect(c).toBeDefined();
      c.stop();
    });
  });

  // ===========================================================================
  // getLastData
  // ===========================================================================
  describe('getLastData', () => {
    it('should return null before any collection', () => {
      expect(collector.getLastData()).toBeNull();
    });

    it('should return the last collected data', async () => {
      const onData = jest.fn();
      await collector.collectOnce(onData);

      const lastData = collector.getLastData();
      expect(lastData).not.toBeNull();
      expect(lastData!.providerId).toBe('test-node-1');
    });

    it('should return the most recent data after multiple collections', async () => {
      const onData = jest.fn();
      await collector.collectOnce(onData);
      await collector.collectOnce(onData);
      await collector.collectOnce(onData);

      const lastData = collector.getLastData();
      expect(lastData).not.toBeNull();
      expect(lastData!.providerId).toBe('test-node-1');
    });
  });
});
