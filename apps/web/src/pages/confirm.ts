import { confirmRegister } from '../auth';

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('userDetails');
    if (!form) return;

    form.addEventListener('submit', (e: Event) => {
        e.preventDefault();
        const code = (document.getElementById('confirmCode') as HTMLInputElement).value;
        confirmRegister(code);
    });
});
