/**
 * Example: Real-Time Chunk Relay with Confirmation-Based Deletion using IndexCPClient
 *
 * To run:
 *   node examples/uploadMediaStream.js
 *
 * This demo simulates a media stream by creating a Node.js Readable stream
 * that emits random data chunks. It buffers the stream using IndexCPClient.addStream,
 * then demonstrates real-time relay of chunks to an external application (simulated)
 * using relayChunksInOrder. Each chunk is deleted from the local DB only after
 * confirmation from the external application, ensuring reliable, low-latency streaming
 * and efficient storage usage.
 *
 * For a real WebRTC stream, replace the simulated stream with the actual media stream’s readable interface.
 * The external application logic can be replaced with real network calls or IPC as needed.
 */

const { Readable } = require('stream');
const IndexCPClient = require('../lib/client');

// Simulate a media stream: emits 100 random 512-byte chunks
class RandomMediaStream extends Readable {
  constructor(options = {}) {
    super(options);
    this.chunks = options.chunks || 100;
    this.chunkSize = options.chunkSize || 512;
    this.sent = 0;
  }
  _read() {
    if (this.sent >= this.chunks) {
      this.push(null); // end
      return;
    }
    const buf = Buffer.alloc(this.chunkSize);
    for (let i = 0; i < this.chunkSize; i++) {
      buf[i] = Math.floor(Math.random() * 256);
    }
    this.push(buf);
    this.sent++;
  }
}

async function main() {
  const client = new IndexCPClient();
  const sessionId = 'session-' + Date.now();
  const streamName = 'simulated-media';
  const mediaStream = new RandomMediaStream({ chunks: 100, chunkSize: 512 });

  console.log(`Buffering simulated media stream as '${streamName}' with sessionId '${sessionId}'...`);
  const chunkCount = await client.addStream(mediaStream, streamName, sessionId);
  console.log(`Buffered ${chunkCount} chunks for stream '${streamName}' (session: ${sessionId})`);

  // --- Real-Time Chunk Relay with Confirmation-Based Deletion ---
  // Simulate an external application relay with async confirmation
  async function onChunk(chunkData, meta) {
    // Simulate sending chunk to external app (e.g., network, IPC, etc.)
    console.log(`[relay-demo] Relaying chunk ${meta.chunkIndex} (id: ${meta.id}) to external app...`);
    // Simulate async confirmation (e.g., network round-trip)
    await new Promise(res => setTimeout(res, 50));
    // Always confirm for demo
    console.log(`[relay-demo] External app confirmed chunk ${meta.chunkIndex} (id: ${meta.id})`);
    return true;
  }

  // Relay options (configurable)
  const relayOptions = {
    fileName: streamName,
    sessionId,
    onChunk,
    maxRetries: 5,
    retryDelay: 200, // ms
  };

  console.log(`\n[relay-demo] Starting real-time relay for stream '${streamName}' (session: ${sessionId})...`);
  // Start relay loop (will exit when all chunks relayed and deleted)
  await client.relayChunksInOrder(relayOptions);
  console.log(`[relay-demo] All chunks relayed and deleted for stream '${streamName}' (session: ${sessionId})`);
}

main().catch(err => {
  console.error('Error in real-time relay demo:', err);
  process.exit(1);
});
