function startVoice() {
  const rec = new webkitSpeechRecognition();
  rec.lang = "en-IN";

  rec.onresult = (e) => {
    const text = e.results[0][0].transcript;
    document.getElementById("commodity").value = text.charAt(0).toUpperCase() + text.slice(1);
  };

  rec.start();
}
