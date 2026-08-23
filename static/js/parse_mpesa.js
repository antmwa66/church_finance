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
        console.log('Parsed data:', data); // Debug logging
        if (data.error) {
            status.textContent = data.error;
            status.style.color = 'red';
            return;
        }

        // Clear previous values first
        document.getElementById('amount').value = '';
        document.getElementById('receipt_reference').value = '';
        const paybill = document.getElementById('paybill_number');
        if (paybill) paybill.value = '';
        const sel = document.getElementById('category_id');
        if (sel) sel.value = '';

        // Set new values
        if (data.amount) {
            document.getElementById('amount').value = data.amount;
            console.log('Set amount:', data.amount);
        }
        if (data.transaction_code) {
            document.getElementById('receipt_reference').value = data.transaction_code;
            console.log('Set transaction code:', data.transaction_code);
        }

        if (paybill && data.paybill_number) {
            paybill.value = data.paybill_number;
            console.log('Set paybill:', data.paybill_number);
        }

        if (data.payment_date) {
            document.getElementById('payment_date').value = data.payment_date;
            console.log('Set payment date:', data.payment_date);
        }

        if (sel && data.category) {
            for (const opt of sel.options) {
                if (opt.text.trim().toLowerCase() === data.category.toLowerCase()) {
                    sel.value = opt.value;
                    console.log('Set category:', data.category);
                    break;
                }
            }
        }

        let notes = '';
        if (data.sender_name) notes += 'Sender: ' + data.sender_name + (data.sender_phone ? ' (' + data.sender_phone + ')' : '');
        if (data.payment_time) notes += (notes ? '; ' : '') + 'Time: ' + data.payment_time;
        if (notes) document.getElementById('notes').value = notes;

        status.textContent = 'Parsed successfully. Amount: ' + (data.amount || 'N/A') + ', Category: ' + (data.category || 'N/A') + ', Paybill: ' + (data.paybill_number || 'N/A');
        status.style.color = 'green';
    })
    .catch(err => {
        status.textContent = 'Failed to parse message.';
        status.style.color = 'red';
    });
}
