import { useUi, uiStore } from '../../stores/uiStore';

export default function Toasts() {
  const { toasts } = useUi();
  if (!toasts.length) return null;
  return (
    <div className="toasts">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast${toast.bad ? ' bad' : ''}`} onClick={() => uiStore.dismiss(toast.id)}>
          {toast.text}
        </div>
      ))}
    </div>
  );
}
