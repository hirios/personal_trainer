const express = require("express");
const path = require("path");

const app = express();

const FRONTEND_DIR = __dirname;

// serve normalmente
app.use(express.static(FRONTEND_DIR));

// í´¥ alias para corrigir /frontend/*
app.use("/frontend", express.static(FRONTEND_DIR));

// rotas
app.get("/", (req, res) => {
  res.sendFile(path.join(FRONTEND_DIR, "public/login.html"));
});

app.listen(3000, () => {
  console.log("Servidor rodando em http://localhost:3000");
});
