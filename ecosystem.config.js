module.exports = {
  apps: [{
    name: "forexpullback",
    script: "main.py",
    interpreter: "./venv/bin/python",
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      PYTHONUNBUFFERED: "1"
    }
  }]
};
