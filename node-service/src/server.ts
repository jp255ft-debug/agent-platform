import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';
import * as path from 'path';
import * as os from 'os';
import { logger } from './logger';
import { GPUCollector, GPUInfo } from './gpu_collector';
import { KafkaPublisher } from './kafka_publisher';

// =============================================================================
// Agent Platform — Node Service (gRPC Server)
// =============================================================================
// This service:
//   1. Runs a gRPC server that receives GPU health reports from DePIN nodes
//   2. Runs a GPU collector that gathers local telemetry via NVML/systeminformation
//   3. Publishes all telemetry to Kafka for backend consumption
// =============================================================================

// ─── Configuration ──────────────────────────────────────────────────────────

interface NodeServiceConfig {
  grpcPort: number;
  providerId: string;
  collectionIntervalMs: number;
  gpuIndex: number;
  kafkaBrokers: string[];
  enableGPUCollector: boolean;
  enableGRPCServer: boolean;
}

function loadConfig(): NodeServiceConfig {
  return {
    grpcPort: parseInt(process.env.GRPC_PORT || '50051', 10),
    providerId: process.env.PROVIDER_ID || `node-${os.hostname()}`,
    collectionIntervalMs: parseInt(process.env.COLLECTION_INTERVAL_MS || '30000', 10),
    gpuIndex: parseInt(process.env.GPU_INDEX || '0', 10),
    kafkaBrokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
    enableGPUCollector: process.env.GPU_COLLECTOR_ENABLED === 'true',
    enableGRPCServer: process.env.GRPC_SERVER_ENABLED !== 'false',
  };
}

// ─── gRPC Server ────────────────────────────────────────────────────────────

class GRPCServer {
  private server: grpc.Server;
  private config: NodeServiceConfig;
  private latestReports: Map<string, GPUInfo> = new Map();

  constructor(config: NodeServiceConfig) {
    this.config = config;
    this.server = new grpc.Server();
  }

  /**
   * Start the gRPC server.
   */
  async start(): Promise<void> {
    const protoPath = path.resolve(__dirname, 'proto', 'telemetry.proto');
    const packageDefinition = protoLoader.loadSync(protoPath, {
      keepCase: true,
      longs: String,
      enums: String,
      defaults: true,
      oneofs: true,
    });

    const protoDescriptor = grpc.loadPackageDefinition(packageDefinition) as any;
    const telemetryPackage = protoDescriptor.agent_platform.telemetry;

    this.server.addService(telemetryPackage.GPUTelemetry.service, {
      reportGPUHealth: this.handleReportGPUHealth.bind(this),
      getGPUStatus: this.handleGetGPUStatus.bind(this),
    });

    return new Promise((resolve, reject) => {
      this.server.bindAsync(
        `0.0.0.0:${this.config.grpcPort}`,
        grpc.ServerCredentials.createInsecure(),
        (error, port) => {
          if (error) {
            logger.error('Failed to bind gRPC server', { error: String(error) });
            reject(error);
            return;
          }
          this.server.start();
          logger.info('gRPC server started', { port: this.config.grpcPort });
          resolve();
        }
      );
    });
  }

  /**
   * Stop the gRPC server.
   */
  async stop(): Promise<void> {
    return new Promise((resolve) => {
      this.server.tryShutdown(() => {
        logger.info('gRPC server stopped');
        resolve();
      });
    });
  }

  /**
   * Handle streaming GPU health reports from provider nodes.
   */
  private handleReportGPUHealth(call: any): void {
    const providerId = call.metadata.get('provider-id')[0] || 'unknown';

    logger.info('GPU health stream started', { providerId });

    call.on('data', (report: any) => {
      const gpuInfo: GPUInfo = {
        providerId: report.provider_id || providerId,
        gpuModel: report.gpu_model || 'unknown',
        gpuUtilization: report.gpu_utilization || 0,
        temperatureCelsius: report.temperature_celsius || 0,
        memoryUsedGb: report.memory_used_gb || 0,
        memoryTotalGb: report.memory_total_gb || 0,
        powerWatts: report.power_watts || 0,
        uptimeSeconds: report.uptime_seconds || 0,
        timestamp: report.timestamp || Math.floor(Date.now() / 1000),
        tflopsFp16: report.tflops_fp16 || 0,
        activeJobs: report.active_jobs || 0,
        status: report.status || 'online',
        labels: report.labels || {},
      };

      this.latestReports.set(gpuInfo.providerId, gpuInfo);
      logger.debug('Received GPU health report', {
        providerId: gpuInfo.providerId,
        gpuUtilization: gpuInfo.gpuUtilization,
        status: gpuInfo.status,
      });
    });

    call.on('end', () => {
      logger.info('GPU health stream ended', { providerId });
      call.write({
        accepted: true,
        message: 'Reports received successfully',
        processed_at: Math.floor(Date.now() / 1000),
      });
      call.end();
    });

    call.on('error', (error: Error) => {
      logger.error('GPU health stream error', { providerId, error: String(error) });
    });
  }

  /**
   * Handle GPU status queries.
   */
  private handleGetGPUStatus(call: any, callback: any): void {
    const providerId = call.request.provider_id;
    const report = this.latestReports.get(providerId);

    if (!report) {
      callback(null, {
        provider_id: providerId,
        gpu_model: 'unknown',
        gpu_utilization: 0,
        temperature_celsius: 0,
        memory_used_gb: 0,
        memory_total_gb: 0,
        status: 'offline',
        last_report_at: 0,
        uptime_seconds: 0,
      });
      return;
    }

    callback(null, {
      provider_id: report.providerId,
      gpu_model: report.gpuModel,
      gpu_utilization: report.gpuUtilization,
      temperature_celsius: report.temperatureCelsius,
      memory_used_gb: report.memoryUsedGb,
      memory_total_gb: report.memoryTotalGb,
      status: report.status,
      last_report_at: report.timestamp,
      uptime_seconds: report.uptimeSeconds,
    });
  }
}

// ─── Main Application ───────────────────────────────────────────────────────

async function main(): Promise<void> {
  const config = loadConfig();

  logger.info('Starting Node Service', {
    providerId: config.providerId,
    grpcPort: config.grpcPort,
    collectionIntervalMs: config.collectionIntervalMs,
    gpuIndex: config.gpuIndex,
    kafkaBrokers: config.kafkaBrokers,
    enableGPUCollector: config.enableGPUCollector,
    enableGRPCServer: config.enableGRPCServer,
  });

  // Initialize Kafka publisher
  const kafkaPublisher = new KafkaPublisher({
    brokers: config.kafkaBrokers,
  });

  try {
    await kafkaPublisher.connect();
  } catch (error) {
    logger.warn('Kafka connection failed, continuing without Kafka', {
      error: String(error),
    });
  }

  // Initialize GPU collector (if enabled)
  if (config.enableGPUCollector) {
    const gpuCollector = new GPUCollector({
      providerId: config.providerId,
      collectionIntervalMs: config.collectionIntervalMs,
      gpuIndex: config.gpuIndex,
    });

    gpuCollector.start(async (data: GPUInfo) => {
      await kafkaPublisher.publishHealthReport(data);
    });

    // Handle graceful shutdown
    const shutdown = async () => {
      logger.info('Shutting down...');
      gpuCollector.stop();
      await kafkaPublisher.disconnect();
      process.exit(0);
    };

    process.on('SIGINT', shutdown);
    process.on('SIGTERM', shutdown);
  }

  // Initialize gRPC server (if enabled)
  if (config.enableGRPCServer) {
    const grpcServer = new GRPCServer(config);
    await grpcServer.start();

    // Keep the process alive
    const keepAlive = setInterval(() => {}, 1 << 30);
    process.on('SIGINT', () => {
      clearInterval(keepAlive);
      grpcServer.stop().then(() => process.exit(0));
    });
    process.on('SIGTERM', () => {
      clearInterval(keepAlive);
      grpcServer.stop().then(() => process.exit(0));
    });
  }

  // If neither collector nor gRPC is enabled, warn and exit
  if (!config.enableGPUCollector && !config.enableGRPCServer) {
    logger.warn('Neither GPU collector nor gRPC server is enabled. Exiting.');
    process.exit(0);
  }
}

// Run the application
main().catch((error) => {
  logger.error('Fatal error', { error: String(error) });
  process.exit(1);
});
