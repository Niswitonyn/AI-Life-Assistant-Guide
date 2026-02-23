export default function GmailSetup({ next }) {

  const handleUpload = async (file) => {

    const form = new FormData();
    form.append("file", file);

    await fetch("http://127.0.0.1:8000/api/setup/gmail", {
      method: "POST",
      body: form
    });

    next();
  };

  return (
    <div>
      <h2>Connect Gmail</h2>

      <p>Upload your Google credentials.json</p>

      <input
        type="file"
        accept=".json"
        onChange={(e) => handleUpload(e.target.files[0])}
      />
    </div>
  );
}