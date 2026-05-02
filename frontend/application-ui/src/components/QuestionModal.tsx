import { useRef } from "react";
import { MessageCircleQuestion } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { FrontendRequest } from "../types/protocol";
import { Overlay } from "./PermissionModal";

interface QuestionModalProps {
  requestId: string;
  question: string;
  onSend: (req: FrontendRequest) => void;
  onDismiss: () => void;
}

export default function QuestionModal({
  requestId,
  question,
  onSend,
  onDismiss,
}: QuestionModalProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const answer = inputRef.current?.value.trim() ?? "";
    onSend({ type: "question_response", request_id: requestId, answer });
    onDismiss();
  };

  return (
    <Overlay>
      <div className="w-[min(440px,90vw)] max-h-[80vh] overflow-y-auto bg-bg-tertiary border border-border-primary rounded-xl p-6">
        <div className="flex items-center gap-2 mb-3">
          <MessageCircleQuestion className="size-5 text-role-user" />
          <span className="text-[15px] font-semibold text-role-user">
            Question
          </span>
        </div>
        <div className="bg-bg-code p-2.5 rounded-md text-[13px] text-text-secondary whitespace-pre-wrap mb-3">
          {question}
        </div>
        <textarea
          ref={inputRef}
          autoFocus
          rows={3}
          placeholder="Type your answer…"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          className="w-full p-2.5 rounded-md border border-border-primary bg-bg-page text-text-primary text-[13px] resize-y font-sans mb-3 outline-none focus:border-accent-blue transition-colors"
        />
        <div className="flex gap-2 justify-end">
          <Button onClick={submit}>
            Submit
          </Button>
        </div>
      </div>
    </Overlay>
  );
}
