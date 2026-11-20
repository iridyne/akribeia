import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

export default function promptAssert(pi: ExtensionAPI): void {
	let printed = false;
	pi.on("before_provider_request", async ({ payload }) => {
		if (printed) return;
		printed = true;
		const s = JSON.stringify(payload);
		const checks: [string, boolean][] = [
			["rule1-doubt-them", s.includes("NEVER rerun checks to doubt them")],
			["rule2-add-avoidable", s.includes("NEVER add avoidable allocation")],
			["rule4-devices-not-functions", s.includes("Devices are not functions")],
			["delta-reminder", s.includes("omp-config/system-prompt-replace")],
			["model-delta", s.includes("文件检查只用 `read`/`grep`/`glob`")],
			["one-shot-conclusion", s.includes("禁止以原始工具输出结束回合")],
			["read-exception", s.includes("read 不可达")],
			["rules-permission-exception", s.includes("权限例外")],
			["rules-probe-conclusion", s.includes("结果到达即收口")],
			["repo-rules-relative", s.includes('<context-file path=\\"AGENTS.md\\">')],
		];
		for (const [name, value] of checks) process.stderr.write(`ASSERT ${name}=${value}\n`);
	});
}