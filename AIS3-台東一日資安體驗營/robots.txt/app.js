const express = require("express");
const app = express();
const PORT = 10001;

// /robots.txt → hints at the hidden path
app.get("/robots.txt", (req, res) => {
  res.type("text/plain").send(
    "User-agent: *\n" +
    "Disallow: /meowowowo\n"
  );
});

// /meowowowo → the "forbidden" page
app.get("/meowowowo", (req, res) => {
  res.type("text/plain; charset=utf-8").send(
    "不是跟你說了不可以嗎！壞壞！\n\n" +
    "Flag: AIS3{r0b0ts_txt_1s_n0t_s3cur1ty}\n"
  );
});

// / → landing page
app.get("/", (req, res) => {
  res.type("text/plain; charset=utf-8").send(
    "Welcome! There's nothing here... or is there?\n\n" +
    "Hint: What file do websites use to tell crawlers where NOT to go?\n"
  );
});

app.listen(PORT, () => {
  console.log("Lab3 running on http://localhost:" + PORT);
});
