export function getEstimatorAgentId(): string | undefined {
  return process.env.NEXT_PUBLIC_ELEVENLABS_ESTIMATOR_AGENT_ID;
}

export function isAgentIdConfigured(): boolean {
  const id = getEstimatorAgentId();
  return Boolean(id) && !id!.includes("placeholder");
}
