const net = require("net");
const http = require("http");
const express = require("express");
const app = express();
const PORT = 10000;

// ===== ASCII Art =====

const CAT_ART = [
  "",
  "   /\\_/\\  ",
  "  ( o.o ) ",
  "   > ^ <  ",
  "  /|   |\\ ",
  " (_|   |_)",
  '    " "   ',
  "",
  "  Meow~ You found the secret method!",
].join("\n");

const BANNER = [
  "",
  "==============================================",
  "       HTTP Method Discovery Lab",
  "       AIS3 東部資安體驗營",
  "==============================================",
  "",
  "Welcome! Your mission:",
  "  Use curl to discover which HTTP method returns the flag.",
  "",
  "Hints:",
  "  1. Try:  curl -X OPTIONS http://localhost:" + PORT + "/",
  '  2. Read the "Allow" header carefully',
  "  3. Not every method is standard... some are custom ;)",
  "",
  "Good luck!",
].join("\n");

// ===== Express Routes (standard HTTP methods) =====

app.options("/", (req, res) => {
  res.set("Allow", "GET, POST, OPTIONS, MEOW");
  res.type("text/plain").send(
    [
      "Allowed methods: GET, POST, OPTIONS, MEOW",
      "",
      "Hint: Try each method and see what happens!",
      "Usage: curl -X METHOD http://localhost:" + PORT + "/",
    ].join("\n")
  );
});

app.get("/", (req, res) => {
  res.type("text/plain").send(
    [
      BANNER,
      "",
      "You used GET. That's the default, but not the answer.",
      "",
      "Tip: curl -X OPTIONS http://localhost:" + PORT + "/",
    ].join("\n")
  );
});

app.post("/", (req, res) => {
  res.type("text/plain").send(
    [
      "You used POST. Nice try, but still not the right one.",
      "",
      "Hint: Did you check OPTIONS yet?",
      "  curl -X OPTIONS http://localhost:" + PORT + "/",
    ].join("\n")
  );
});

app.all("/", (req, res) => {
  res.type("text/plain").send(
    [
      "You used " + req.method + ". Interesting, but not quite.",
      "",
      "Have you tried OPTIONS to see what's available?",
    ].join("\n")
  );
});

// ===== Internal HTTP server (no listen — used via emit) =====

const httpServer = http.createServer(app);

// ===== Raw TCP Server =====
// Node's HTTP parser rejects non-standard methods even with
// insecureHTTPParser. So we read raw bytes from the socket,
// peek at the method, and either handle it ourselves (MEOW)
// or hand off to the HTTP server for standard methods.

const tcpServer = net.createServer((socket) => {
  let buffer = Buffer.alloc(0);

  socket.once("data", (chunk) => {
    buffer = Buffer.concat([buffer, chunk]);
    const head = buffer.toString("utf-8", 0, Math.min(buffer.length, 512));
    const firstLine = head.split("\r\n")[0] || "";
    const method = firstLine.split(" ")[0] || "";

    if (method === "MEOW") {
      // Handle custom method directly at TCP level
      const body = [
        CAT_ART,
        "",
        "Flag: AIS3{m30w_http_m3th0d_m4st3r}",
        "",
        "--- What did you learn? ---",
        "",
        "HTTP methods are just strings in the request line.",
        "curl -X lets you send ANY string as a method.",
        "Servers can define custom methods, and attackers",
        "can send unexpected ones. Always validate!",
      ].join("\n");

      const response = [
        "HTTP/1.1 200 OK",
        "Content-Type: text/plain; charset=utf-8",
        "Content-Length: " + Buffer.byteLength(body),
        "Connection: close",
        "",
        body,
      ].join("\r\n");

      socket.end(response);
    } else {
      // Standard method → feed to Node's HTTP server
      // Re-emit the data we already consumed
      httpServer.emit("connection", socket);
      socket.unshift(buffer);
    }
  });

  socket.on("error", () => {});
});

tcpServer.listen(PORT, () => {
  console.log("");
  console.log("==================================================");
  console.log("  HTTP Method Discovery Lab is running!");
  console.log("  http://localhost:" + PORT);
  console.log("==================================================");
  console.log("");
  console.log("Students should start with:");
  console.log("  curl http://localhost:" + PORT + "/");
  console.log("");
});
