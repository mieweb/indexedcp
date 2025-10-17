// Example: Using ignore mode (default) with original filenames preserved

const { IndexedCPServer } = require('../lib/server');

// Create server with 'ignore' mode (the default)
// This generates unique filenames while preserving original names for traceability
const server = new IndexedCPServer({
  port: 3000,
  outputDir: './uploads',
  // pathMode: 'ignore' is the default, so we don't need to specify it
  apiKey: 'demo-api-key-12345'
});

server.listen(3000, () => {
  console.log('\n🔒 Server running in IGNORE mode (default)');
  console.log('   Filenames will be: <timestamp>_<random>_<full-path>.<ext>');
  console.log('\nExamples of what gets saved:');
  console.log('   Client sends: report.pdf');
  console.log('   Server saves: 1234567890_a1b2c3d4_report.pdf\n');
  console.log('   Client sends: documents/final version.docx');
  console.log('   Server saves: 1234567890_e5f6g7h8_documents_final-version.docx\n');
  console.log('   Client sends: reports/2024/Q1/data.csv');
  console.log('   Server saves: 1234567890_i9j0k1l2_reports_2024_Q1_data.csv\n');
  console.log('Benefits:');
  console.log('   ✓ Guaranteed unique filenames (no overwrites)');
  console.log('   ✓ Full path preserved for complete traceability');
  console.log('   ✓ Path separators (_) vs special chars (-) for easy parsing');
  console.log('   ✓ Timestamp for chronological sorting');
  console.log('   ✓ Random component for extra uniqueness');
  console.log('   ✓ Perfect for audit trails and databases\n');
  console.log('Press Ctrl+C to stop');
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\n\nShutting down...');
  server.close();
  process.exit(0);
});
