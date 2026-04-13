module.exports = {
  extends: ["@commitlint/config-conventional"],
  // Only lint commits that attempt conventional format (type: or type(scope):).
  // This skips legacy commits, auto-generated merge commits, Linear-prefixed
  // commits (G-NNN:), and other pre-commitlint messages in the branch history.
  ignores: [
    (message) => !/^[a-z]+(\([^)]*\))?!?:\s/.test(message.split("\n")[0]),
  ],
  rules: {
    "type-enum": [
      2,
      "always",
      [
        "build",
        "chore",
        "ci",
        "deps",
        "docs",
        "feat",
        "fix",
        "merge",
        "perf",
        "refactor",
        "revert",
        "style",
        "test",
      ],
    ],
    "subject-case": [0],
    "body-max-line-length": [0],
    "footer-leading-blank": [0],
  },
};
