type Props = {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
};

export function Switch({ checked, onChange, label }: Props) {
  return (
    <label className="inline-flex cursor-pointer select-none items-center gap-2 text-sm text-neutral-700">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-4 w-7 flex-shrink-0 rounded-full transition-colors ${
          checked ? "bg-neutral-900" : "bg-neutral-300"
        }`}
      >
        <span
          className={`inline-block h-3 w-3 transform rounded-full bg-white shadow-sm transition-transform ${
            checked ? "translate-x-3.5" : "translate-x-0.5"
          } mt-0.5`}
          aria-hidden
        />
      </button>
      <span>{label}</span>
    </label>
  );
}
