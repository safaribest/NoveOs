#!/usr/bin/env node
/**
 * Claude Code --bare 启动包装器 (Node.js 版本)
 * 解决 Windows 下 .bat 文件 spawn EINVAL 问题
 */

const { spawn } = require('child_process');
const path = require('path');

const DEFAULT_CLAUDE = 'C:\\Users\\z60063357\\.vscode\\extensions\\anthropic.claude-code-2.1.181-win32-x64\\resources\\native-binary\\claude.exe';

let claudeExe = DEFAULT_CLAUDE;
const args = ['--bare'];

// 如果第一个参数是 claude.exe 路径，使用它
if (process.argv.length > 2) {
    const firstArg = process.argv[2];
    if (path.basename(firstArg).toLowerCase() === 'claude.exe' && require('fs').existsSync(firstArg)) {
        claudeExe = firstArg;
        // 剩余参数传给 claude
        for (let i = 3; i < process.argv.length; i++) {
            args.push(process.argv[i]);
        }
    } else {
        // 所有参数传给 claude
        for (let i = 2; i < process.argv.length; i++) {
            args.push(process.argv[i]);
        }
    }
}

const child = spawn(claudeExe, args, {
    stdio: 'inherit',
    env: {
        ...process.env,
        ANTHROPIC_BASE_URL: 'http://127.0.0.1:3456',
        ANTHROPIC_API_KEY: 'sk-df45c60ea15c433ab35ecf430190d5be',
        CLAUDE_CODE_SIMPLE: '1'
    }
});

child.on('exit', (code) => {
    process.exit(code ?? 0);
});
