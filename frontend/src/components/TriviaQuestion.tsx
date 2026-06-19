import { useState } from "react";

export interface Question {
  type: "multiple_choice" | "true_false" | "guess_player";
  question: string;
  options: string[];
  answer: string;
  explanation: string;
  difficulty: string;
}

interface Props {
  question: Question;
  number: number;
  total: number;
  onAnswer: (correct: boolean) => void;
}

export function TriviaQuestion({ question, number, total, onAnswer }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(false);

  const handleSelect = (option: string) => {
    if (revealed) return;
    setSelected(option);
    setRevealed(true);
    const correct = option.trim().toLowerCase() === question.answer.trim().toLowerCase();
    setTimeout(() => onAnswer(correct), 1200);
  };

  const isCorrect = (option: string) =>
    option.trim().toLowerCase() === question.answer.trim().toLowerCase();

  return (
    <div className="flex-1 flex flex-col p-8 max-w-2xl mx-auto w-full">
      <div className="font-mono text-xs text-text-secondary tracking-wider mb-6">
        QUESTION {number} OF {total}
      </div>

      <div className="text-xl font-bold leading-snug mb-8">
        {question.question}
      </div>

      <div className="flex flex-col gap-3">
        {question.options.map((option, idx) => {
          let borderColor = "border-[#2A2E3D]";
          let textColor = "text-text-primary";
          let bg = "";

          if (revealed) {
            if (isCorrect(option)) {
              borderColor = "border-prob-win";
              textColor = "text-prob-win";
              bg = "bg-[#0d2b1a]";
            } else if (option === selected && !isCorrect(option)) {
              borderColor = "border-prob-loss";
              textColor = "text-prob-loss";
              bg = "bg-[#2b0d0d]";
            } else {
              textColor = "text-text-secondary";
            }
          }

          return (
            <button
              key={idx}
              onClick={() => handleSelect(option)}
              disabled={revealed}
              className={`w-full text-left px-5 py-4 border ${borderColor} ${textColor} ${bg} font-mono text-sm transition-all hover:border-text-secondary disabled:cursor-default`}
            >
              <span className="text-text-secondary mr-3">
                {String.fromCharCode(65 + idx)}.
              </span>
              {option}
            </button>
          );
        })}
      </div>

      {revealed && (
        <div className="mt-6 p-4 border border-[#1F2230] bg-[#15171F]">
          <div className={`font-mono text-xs tracking-wider mb-2 ${isCorrect(selected ?? "") ? "text-prob-win" : "text-prob-loss"}`}>
            {isCorrect(selected ?? "") ? "✓ CORRECT" : `✗ CORRECT ANSWER: ${question.answer}`}
          </div>
          <div className="text-sm text-text-secondary leading-relaxed">
            {question.explanation}
          </div>
        </div>
      )}
    </div>
  );
}