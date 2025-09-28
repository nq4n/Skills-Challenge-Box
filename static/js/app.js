function copyText(text){
  navigator.clipboard.writeText(text).then(()=>{
    alert("Copied!");
  });
}
function markCompleted(code){
  const key = "scb_completed_"+code;
  localStorage.setItem(key, "1");
  alert("Marked as completed (demo only).");
}
