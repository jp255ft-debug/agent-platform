import { Kafka, Producer, ProducerRecord, Message } from 'kafkajs';
import { logger } from './logger';
import { GPUInfo } from './gpu_collector';

// =============================================================================
// Agent Platform — Kafka Publisher
// =============================================================================
// Publishes GPU telemetry data to Kafka for consumption by the backend.
// Topics:
//   - depin.provider.health    : GPU health reports from provider nodes
//   - depin.provider.status    : Provider status changes (online/degraded/offline)
// =============================================================================

export interface KafkaPublisherConfig {
  brokers: string[];
  clientId: string;
  healthTopic: string;
  statusTopic: string;
}

const DEFAULT_CONFIG: KafkaPublisherConfig = {
  brokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
  clientId: 'node-service',
  healthTopic: 'depin.provider.health',
  statusTopic: 'depin.provider.status',
};

export class KafkaPublisher {
  private kafka: Kafka;
  private producer: Producer;
  private config: KafkaPublisherConfig;
  private connected: boolean = false;
  private lastStatus: Map<string, GPUInfo['status']> = new Map();

  constructor(config?: Partial<KafkaPublisherConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };

    this.kafka = new Kafka({
      clientId: this.config.clientId,
      brokers: this.config.brokers,
      retry: {
        initialRetryTime: 1000,
        retries: 10,
        maxRetryTime: 30000,
      },
    });

    this.producer = this.kafka.producer({
      allowAutoTopicCreation: true,
      transactionTimeout: 30000,
    });
  }

  /**
   * Connect to Kafka and start the producer.
   */
  async connect(): Promise<void> {
    try {
      await this.producer.connect();
      this.connected = true;
      logger.info('Connected to Kafka', {
        brokers: this.config.brokers,
        clientId: this.config.clientId,
      });
    } catch (error) {
      logger.error('Failed to connect to Kafka', { error: String(error) });
      throw error;
    }
  }

  /**
   * Disconnect from Kafka.
   */
  async disconnect(): Promise<void> {
    try {
      await this.producer.disconnect();
      this.connected = false;
      logger.info('Disconnected from Kafka');
    } catch (error) {
      logger.error('Error disconnecting from Kafka', { error: String(error) });
    }
  }

  /**
   * Publish a GPU health report to Kafka.
   */
  async publishHealthReport(gpuInfo: GPUInfo): Promise<void> {
    if (!this.connected) {
      logger.warn('Kafka not connected, skipping publish');
      return;
    }

    const message: Message = {
      key: gpuInfo.providerId,
      value: JSON.stringify({
        provider_id: gpuInfo.providerId,
        gpu_model: gpuInfo.gpuModel,
        gpu_utilization: gpuInfo.gpuUtilization,
        temperature_celsius: gpuInfo.temperatureCelsius,
        memory_used_gb: gpuInfo.memoryUsedGb,
        memory_total_gb: gpuInfo.memoryTotalGb,
        power_watts: gpuInfo.powerWatts,
        uptime_seconds: gpuInfo.uptimeSeconds,
        timestamp: gpuInfo.timestamp,
        tflops_fp16: gpuInfo.tflopsFp16,
        active_jobs: gpuInfo.activeJobs,
        status: gpuInfo.status,
        labels: gpuInfo.labels,
      }),
      headers: {
        'content-type': 'application/json',
        'source': 'node-service',
        'provider-id': gpuInfo.providerId,
      },
    };

    const record: ProducerRecord = {
      topic: this.config.healthTopic,
      messages: [message],
    };

    try {
      await this.producer.send(record);
      logger.debug('Published health report', {
        providerId: gpuInfo.providerId,
        status: gpuInfo.status,
        gpuUtilization: gpuInfo.gpuUtilization,
      });
    } catch (error) {
      logger.error('Failed to publish health report', {
        providerId: gpuInfo.providerId,
        error: String(error),
      });
    }

    // Check for status changes and publish status event if needed
    await this.checkStatusChange(gpuInfo);
  }

  /**
   * Detect status changes and publish to the status topic.
   */
  private async checkStatusChange(gpuInfo: GPUInfo): Promise<void> {
    const previousStatus = this.lastStatus.get(gpuInfo.providerId);

    if (previousStatus && previousStatus !== gpuInfo.status) {
      logger.info('Provider status changed', {
        providerId: gpuInfo.providerId,
        from: previousStatus,
        to: gpuInfo.status,
      });

      const statusMessage: Message = {
        key: gpuInfo.providerId,
        value: JSON.stringify({
          provider_id: gpuInfo.providerId,
          previous_status: previousStatus,
          current_status: gpuInfo.status,
          timestamp: gpuInfo.timestamp,
          reason: gpuInfo.status === 'degraded' ? 'High temperature or collection failure' : 'Normal operation',
        }),
        headers: {
          'content-type': 'application/json',
          'source': 'node-service',
          'event-type': 'status-change',
        },
      };

      try {
        await this.producer.send({
          topic: this.config.statusTopic,
          messages: [statusMessage],
        });
      } catch (error) {
        logger.error('Failed to publish status change', {
          providerId: gpuInfo.providerId,
          error: String(error),
        });
      }
    }

    this.lastStatus.set(gpuInfo.providerId, gpuInfo.status);
  }

  /**
   * Check if the producer is connected.
   */
  isConnected(): boolean {
    return this.connected;
  }
}

export default KafkaPublisher;
