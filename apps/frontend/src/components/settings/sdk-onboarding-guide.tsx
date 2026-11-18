export default function SdkOnboardingGuide({ backendUrl }: { backendUrl: string }) {
  return (
    <div className="space-y-4 rounded-lg border border-slate-800 bg-slate-950/40 p-4 text-sm">
      <div>
        <h3 className="mb-1 font-medium text-slate-200">1. Install the SDK</h3>
        <pre className="overflow-x-auto rounded bg-slate-900 p-3 text-xs text-slate-300">
          <code>pip install agentops-sdk-python</code>
        </pre>
      </div>

      <div>
        <h3 className="mb-1 font-medium text-slate-200">2. Configure the endpoint and key</h3>
        <p className="mb-2 text-slate-400">
          Keep the key out of source control - export it as an environment variable:
        </p>
        <pre className="overflow-x-auto rounded bg-slate-900 p-3 text-xs text-slate-300">
          <code>{`export AGENTOPS_API_KEY="<the key you just copied above>"\nexport AGENTOPS_ENDPOINT="${backendUrl}"`}</code>
        </pre>
      </div>

      <div>
        <h3 className="mb-1 font-medium text-slate-200">3. Reference your agent and start an execution</h3>
        <pre className="overflow-x-auto rounded bg-slate-900 p-3 text-xs text-slate-300">
          <code>{`import os
from agentops_sdk import AgentOps

agentops = AgentOps(
    endpoint=os.environ["AGENTOPS_ENDPOINT"],
    api_key=os.environ["AGENTOPS_API_KEY"],
)

# Use the ID of an agent already registered in the Agent Registry.
agent = agentops.agent("<your-agent-id>", version="1.0.0")

with agentops.start_execution(agent=agent, session_id="conversation-123") as execution:
    execution.set_output("Order #4821 confirmed.")

agentops.shutdown()`}</code>
        </pre>
      </div>

      <div>
        <h3 className="mb-1 font-medium text-slate-200">4. Send LLM and tool telemetry</h3>
        <pre className="overflow-x-auto rounded bg-slate-900 p-3 text-xs text-slate-300">
          <code>{`with agentops.start_execution(agent=agent, session_id="conversation-123") as execution:
    with execution.llm_call(model="gpt-4.1", provider="openai") as call:
        response = call_your_llm(...)
        call.set_usage(input_tokens=response.usage.prompt, output_tokens=response.usage.completion)

    with execution.tool_call("lookup_order") as tool:
        result = lookup_order(...)
        tool.set_output(result)  # only type/size is ever recorded, never the value`}</code>
        </pre>
      </div>

      <p className="text-xs text-slate-500">
        See the SDK&apos;s own README (packages/agentops-sdk-python/README.md) for async usage,
        error handling, and the full privacy/security model.
      </p>
    </div>
  );
}
