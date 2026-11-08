/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        accel: {
          red: "#E40000",
          darkred: "#B30000",
          lightred: "#FFF1F1",
          black: "#222222",
          gray: "#F4F5F7",
          border: "#E2E8F0",
        },
      },
      fontSize: {
        base: ["16px", "24px"], // Enforce 16px min body text
      },
      minHeight: {
        tap: "44px", // Minimum tap target
      },
      minWidth: {
        tap: "44px",
      },
    },
  },
  plugins: [],
};
