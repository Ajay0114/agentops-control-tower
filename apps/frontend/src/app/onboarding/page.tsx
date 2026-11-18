import { requireUserOrRedirect } from "@/lib/server/session";
import { BACKEND_API_URL } from "@/lib/server/env";
import OnboardingWizard from "@/components/onboarding/onboarding-wizard";

export default async function OnboardingPage() {
  const user = await requireUserOrRedirect();

  return <OnboardingWizard organizationName={user.organization_name} backendUrl={BACKEND_API_URL} />;
}
