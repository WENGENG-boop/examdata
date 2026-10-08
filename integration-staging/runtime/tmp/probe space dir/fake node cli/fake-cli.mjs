// Synthetic Node CLI used to test the A06 controlled runner (plan 6.4).
//
// This file is NOT the original IELTS/TOEFL aggregator and is not a copy of it.
// It is a zero-dependency stub written for the staging harness so the runner can
// be exercised (argv, cwd, stdout/stderr, exit codes, JSON shape, timeouts,
// cancellation, output bounds) without executing or reading any original Node
// component. It never touches the network, the filesystem, or any data root.
//
// Usage: node fake-cli.mjs <command> [args...]

const [, , command, ...rest] = process.argv;

function out(obj) {
  process.stdout.write(JSON.stringify(obj) + "\n");
}

function err(line) {
  process.stderr.write(line + "\n");
}

const base = {
  ok: true,
  board: "fake",
  command,
  cwd: process.cwd(),
  pid: process.pid,
};

switch (command) {
  case "ok":
    out(base);
    break;

  case "echo":
    out({ ...base, echo: rest });
    break;

  case "env": {
    const env = {};
    for (const name of rest) {
      env[name] = Object.prototype.hasOwnProperty.call(process.env, name)
        ? process.env[name]
        : null;
    }
    out({ ...base, env });
    break;
  }

  case "bad-json":
    process.stdout.write("this is not json at all\n");
    break;

  case "two-values":
    process.stdout.write('{"first":1}\n{"second":2}\n');
    break;

  case "nonzero":
    err("fatal: cannot read C:\\private\\data\\secret.db");
    err("token=SUPERSECRET");
    process.exitCode = 3;
    break;

  case "noisy":
    err("starting fake-cli");
    err("reading C:\\private\\data\\secret.db");
    err("token=SUPERSECRET");
    out({ ...base, note: "logs on stderr" });
    break;

  case "flood": {
    const chunk = "x".repeat(65536);
    process.stdout.write('{"ok":true,"blob":"');
    for (let i = 0; i < 128; i += 1) process.stdout.write(chunk);
    process.stdout.write('"}\n');
    break;
  }

  case "slow":
    setTimeout(() => {
      out({ ...base, late: true });
    }, 600000);
    break;

  case "business-fail":
    out({ ok: false, board: "fake", command, error: "book 99 not found" });
    break;

  case "no-stdout":
    break;

  case "crash":
    process.exitCode = 1;
    break;

  default:
    out({ ...base, ok: false, error: "unknown command" });
    break;
}
