export default function Finish({ onComplete }) {

  return (
    <div>
      <h2>Setup Complete 🎉</h2>

      <button onClick={onComplete}>
        Launch Assistant
      </button>
    </div>
  );
}
