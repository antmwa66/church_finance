function parseMpesaMessage() {
    const message = document.getElementById('mpesa_message').value.trim();
    const status = document.getElementById('parse_status');
    if (!message) {
        status.textContent = 'Please paste a message or code.';
        status.style.color = 'red';
        return;
    }
    status.textContent = 'Parsing...';
    status.style.color = '#1565c0';
    fetch('/api/parse-mpesa-message', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: message})
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            status.textContent = data.error;
            status.style.color = 'red';
            return;
        }
        if (data.amount) document.getElementById('amount').value = data.amount;
        if (data.transaction_code) document.getElementById('receipt_reference').value = data.transaction_code;

        const paybill = document.getElementById('paybill_number');
        if (paybill) paybill.value = '522522';

        if (data.payment_date) document.getElementById('payment_date').value = data.payment_date;

        const sel = document.getElementById('category_id');
        if (sel && data.category) {
            for (const opt of sel.options) {
                if (opt.text.trim().toLowerCase() === data.category.toLowerCase()) {
                    sel.value = opt.value;
                    break;
                }
            }
        }

        let notes = '';
        if (data.sender_name) notes += 'Sender: ' + data.sender_name + (data.sender_phone ? ' (' + data.sender_phone + ')' : '');
        if (data.payment_time) notes += (notes ? '; ' : '') + 'Time: ' + data.payment_time;
        if (notes) document.getElementById('notes').value = notes;

        status.textContent = 'Parsed successfully.';
        status.style.color = 'green';
    })
    .catch(err => {
        status.textContent = 'Failed to parse message.';
        status.style.color = 'red';
    });
}
