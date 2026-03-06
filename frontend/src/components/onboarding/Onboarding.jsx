import { useState } from "react";
import UserSetup from "./UserSetup";
import GmailSetup from "./GmailSetup";
import AISetup from "./AISetup";
import Finish from "./Finish";

export default function Onboarding({ onComplete }) {

  const [step, setStep] = useState(1);

  return (
    <div style={{ padding: 40 }}>

      {step === 1 && <UserSetup next={() => setStep(2)} />}
      {step === 2 && <GmailSetup next={() => setStep(3)} />}
      {step === 3 && <AISetup next={() => setStep(4)} />}
      {step === 4 && <Finish onComplete={onComplete} />}

    </div>
  );
}