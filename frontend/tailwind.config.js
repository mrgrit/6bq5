/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: { 50: '#f5f7fa', 100: '#e9eef5', 900: '#0b1020', 950: '#070a14' },
        attack: { 500: '#ef4444', 600: '#dc2626' },
        defense: { 500: '#22c55e', 600: '#16a34a' },
        kg: { 500: '#6366f1', 600: '#4f46e5' },
      },
    },
  },
  plugins: [],
}
