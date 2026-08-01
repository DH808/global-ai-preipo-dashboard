const { Readable } = require('stream');
const { server } = require('../server');

async function request(path, method = 'GET', body = '') {
  return new Promise((resolve, reject) => {
    const req = new Readable({ read() { this.push(body || null); this.push(null); } });
    req.method = method;
    req.url = path;
    req.headers = { host: 'local.test', 'content-type': 'application/json' };
    const chunks = [];
    const res = {
      statusCode: 200,
      headers: {},
      writeHead(status, headers) { this.statusCode = status; this.headers = headers || {}; },
      write(chunk) { chunks.push(Buffer.from(chunk)); },
      end(chunk) {
        if (chunk) chunks.push(Buffer.from(chunk));
        const text = Buffer.concat(chunks).toString('utf8');
        let payload = text;
        try { payload = JSON.parse(text); } catch (_) {}
        resolve({ status: this.statusCode, payload });
      }
    };
    try { server.emit('request', req, res); } catch (error) { reject(error); }
  });
}

(async () => {
  const input = JSON.parse(process.argv[2]);
  const result = await request(input.path, input.method || 'GET', input.body || '');
  process.stdout.write(JSON.stringify(result));
})().catch(error => {
  process.stderr.write(String(error.stack || error));
  process.exit(1);
});
