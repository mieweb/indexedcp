// relay-media-to-ozwell.js
//
// Example: Relay media stream chunks to Ozwell using multipart/form-data POST.
//
// Usage:
//   1. Set OZ_ENDPOINT and (optionally) OZ_API_KEY at the top of this file or via environment variables.
//   2. Run: node relay-media-to-ozwell.js
//
// This script simulates a media stream (Node.js Readable) and demonstrates:
//   - Buffering the stream into IndexedDB using addStream
//   - Relaying chunks in order to Ozwell using relayChunksInOrder
//   - Sending each chunk as multipart/form-data
//   - Deleting each chunk only after Ozwell confirms receipt
//   - Handling end-of-stream marker

const IndexCPClient = require('../lib/client');
const { Readable } = require('stream');
const FormData = require('form-data');
const fetch = require('node-fetch');

// === CONFIGURATION ===
const OZ_ENDPOINT = process.env.OZ_ENDPOINT || 'https://ozwell.example.com/api/upload';
const OZ_API_KEY = process.env.OZ_API_KEY || '';
const STREAM_NAME = 'demo-media-stream';
const SESSION_ID = 'session-123';
const IS_AUDIO = true; // or false
const CHUNK_COUNT = 5; // Number of chunks to simulate
const CHUNK_SIZE = 1024 * 32; // 32KB per chunk

// === Simulate a Node.js Readable media stream ===
function createSimulatedMediaStream(chunkCount, chunkSize) {
  let sent = 0;
  return new Readable({
    read() {
      if (sent < chunkCount) {
        const buf = Buffer.alloc(chunkSize, sent % 256);
        this.push(buf);
        sent++;
      } else {
        this.push(null); // End of stream
      }
    }
  });
}

(async () => {
  const client = new IndexCPClient();
  const stream = createSimulatedMediaStream(CHUNK_COUNT, CHUNK_SIZE);
  console.log(`[demo] Buffering simulated media stream: ${STREAM_NAME}, session: ${SESSION_ID}`);
  await client.addStream(stream, STREAM_NAME, SESSION_ID);
  console.log('[demo] Stream buffered. Starting relay to Ozwell...');

  // Relay chunks in order to Ozwell
  await client.relayChunksInOrder({
    fileName: STREAM_NAME,
    sessionId: SESSION_ID,
    onChunk: async (chunk, meta) => {
      // meta: { id, fileName, chunkIndex, sessionId, isEndMarker }
      if (meta.isEndMarker) {
        console.log(`[ozwell] End-of-stream marker for ${meta.fileName} (session: ${meta.sessionId})`);
        // Optionally notify Ozwell of end-of-stream (customize as needed)
        return true; // Confirm deletion of end marker
      }
      // Construct FormData for this chunk
      const form = new FormData();
      form.append('index', meta.chunkIndex);
      form.append('type', 'media');
      form.append('sessionId', meta.sessionId);
      form.append('audio', IS_AUDIO ? 'true' : 'false');
      form.append('id', meta.id);
      form.append('data', chunk, {
        filename: `${meta.fileName}-chunk${meta.chunkIndex}.bin`,
        contentType: 'application/octet-stream'
      });
      // POST to Ozwell
      try {
        const res = await fetch(OZ_ENDPOINT, {
          method: 'POST',
          headers: {
            ...form.getHeaders(),
            ...(OZ_API_KEY ? { 'Authorization': `Bearer ${OZ_API_KEY}` } : {})
          },
          body: form
        });
        if (!res.ok) {
          console.error(`[ozwell] Failed to upload chunk ${meta.chunkIndex}: ${res.status} ${res.statusText}`);
          return false; // Do not delete chunk, will retry
        }
        console.log(`[ozwell] Uploaded chunk ${meta.chunkIndex} (${meta.id}) successfully.`);
        return true; // Confirm deletion
      } catch (err) {
        console.error(`[ozwell] Error uploading chunk ${meta.chunkIndex}:`, err.message);
        return false; // Do not delete chunk, will retry
      }
    }
  });
  console.log('[demo] Relay to Ozwell complete.');
})();
