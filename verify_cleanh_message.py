from backend.time_parse.core import clean_message

test_cases = [
    ("Tenho aniversario do João no", "Tenho aniversario do João"),
    ("Comprar leite para", "Comprar leite"),
    ("Buy milk on", "Buy milk"),
    ("Appointment at", "Appointment"),
    ("Ir al médico", "Ir al médico"), # "al" in middle is not stripped
    ("Ir al médico al", "Ir al médico"), # "al" at end is stripped
    ("Cena con", "Cena"),
    ("Lembrar de", "Lembrar"),
    ("Festa da", "Festa"),
    ("Meeting with", "Meeting"),
    ("Call from", "Call"),
]

all_passed = True
for input_text, expected_output in test_cases:
    actual_output = clean_message(input_text)
    if actual_output == expected_output:
        print(f"✅ PASS: '{input_text}' -> '{actual_output}'")
    else:
        print(f"❌ FAIL: '{input_text}' -> '{actual_output}' (expected '{expected_output}')")
        all_passed = False

if all_passed:
    print("\nAll multi-language preposition tests passed! ✅")
else:
    print("\nSome tests failed. ❌")
