import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { writeFileSync } from "node:fs";

/**
 * Akribeia OMP wire-payload probe.
 *
 * Captures the serialized request payload immediately before provider dispatch
 * and evaluates positive delivery witnesses. Every negative check is paired
 * with a positive witness to prevent vacuous passes (INC-0006).
 *
 * Set AKRIBEIA_DUMP_PAYLOAD=/path/to/out.json to dump the raw payload for
 * provider-agnostic verification via `scripts/payload_gate.py`.
 */
export default function promptAssert(pi: ExtensionAPI): void {
	let printed = false;
	pi.on("before_provider_request", async ({ payload }) => {
		if (printed) return;
		printed = true;

		const dumpPath = process.env.AKRIBEIA_DUMP_PAYLOAD;
		if (dumpPath) {
			writeFileSync(dumpPath, JSON.stringify(payload, null, 2), "utf8");
		}

		const s = JSON.stringify(payload);
		const rule1Delivered = s.includes("NEVER rerun checks to doubt them");
		const rule2Delivered = s.includes("NEVER add avoidable allocation");
		const sprWitnessOk = rule1Delivered && rule2Delivered;

		const checks: [string, boolean][] = [
			["rule1-doubt-them", rule1Delivered],
			["rule2-add-avoidable", rule2Delivered],
			// INC-0006 fix: require positive replacement witness before asserting old reminder absence
			["spr-direct-edit", sprWitnessOk && !s.includes("omp-config/system-prompt-replace")],
			["model-delta", s.includes("文件检查只用 `read`/`grep`/`glob`")],
			["one-shot-conclusion", s.includes("禁止以原始工具输出结束回合")],
			["read-exception", s.includes("read 不可达")],
			["rules-permission-exception", s.includes("权限例外")],
			["rules-probe-conclusion", s.includes("结果到达即收口")],
			["rules-architecture-research", s.includes("架构级未知先查证")],
			["repo-rules-relative", s.includes('<context-file path=\\"AGENTS.md\\">')],
		];
		for (const [name, value] of checks) process.stderr.write(`ASSERT ${name}=${value}\n`);
	});
}
