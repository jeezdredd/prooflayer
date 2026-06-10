from django.core.management.base import BaseCommand

from users.models import User

DEMO_USERS = [
    ("james.hartwell@gmail.com", "hartwell_j", "James", "Hartwell", True),
    ("sofia.reyes@outlook.com", "sofia_reyes", "Sofia", "Reyes", True),
    ("nathan.brooks@proton.me", "nbrooks92", "Nathan", "Brooks", True),
    ("emily.chen@gmail.com", "emilychen", "Emily", "Chen", True),
    ("lucas.petrov@yahoo.com", "lpetrov", "Lucas", "Petrov", True),
    ("amara.osei@gmail.com", "amara_osei", "Amara", "Osei", True),
    ("david.kim@hotmail.com", "dkim_photo", "David", "Kim", True),
    ("isabelle.font@gmail.com", "isafont", "Isabelle", "Font", True),
    ("ryan.murphy@proton.me", "ryanm_dev", "Ryan", "Murphy", True),
    ("priya.sharma@outlook.com", "priya_s", "Priya", "Sharma", True),
    ("marco.deluca@gmail.com", "marcodeluca", "Marco", "De Luca", True),
    ("anna.volkov@gmail.com", "anna_vlk", "Anna", "Volkov", True),
    ("oliver.weiss@yahoo.com", "oliverw", "Oliver", "Weiss", True),
    ("fatima.al-hassan@gmail.com", "fatima_alh", "Fatima", "Al-Hassan", True),
    ("thomas.grant@outlook.com", "tgrant", "Thomas", "Grant", True),
    ("yuki.tanaka@gmail.com", "yukitanaka", "Yuki", "Tanaka", False),
    ("carlos.mendez@hotmail.com", "carlosmendez", "Carlos", "Mendez", False),
    ("sarah.nielsen@gmail.com", "s_nielsen", "Sarah", "Nielsen", False),
    ("jake.oconnor@proton.me", "jake_oc", "Jake", "O'Connor", False),
    ("mia.kovaleva@gmail.com", "mia_kova", "Mia", "Kovaleva", False),
    ("ben.adeyemi@outlook.com", "benadeyemi", "Ben", "Adeyemi", False),
    ("lena.schulz@gmail.com", "lena_schulz", "Lena", "Schulz", False),
    ("alex.torres@yahoo.com", "alex_t99", "Alex", "Torres", False),
    ("nina.patel@gmail.com", "ninapatel", "Nina", "Patel", False),
    ("kevin.larsen@hotmail.com", "klarsen", "Kevin", "Larsen", False),
    ("diana.morin@gmail.com", "dmorin", "Diana", "Morin", False),
    ("sam.wu@proton.me", "samwu_", "Sam", "Wu", False),
    ("julia.baxter@outlook.com", "julia_bx", "Julia", "Baxter", False),
    ("ethan.rose@gmail.com", "ethanrose", "Ethan", "Rose", False),
    ("chloe.lambert@gmail.com", "chloelambert", "Chloe", "Lambert", False),
]

DEFAULT_PASSWORD = "ProofLayer2026!"


class Command(BaseCommand):
    help = "Seed 30 realistic demo users (mix of verified/unverified)"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Delete non-staff users first")

    def handle(self, *args, **opts):
        if opts["clear"]:
            deleted, _ = User.objects.filter(is_staff=False).delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted} non-staff users"))

        created = 0
        skipped = 0
        for email, username, first, last, verified in DEMO_USERS:
            if User.objects.filter(email=email).exists():
                skipped += 1
                continue
            User.objects.create_user(
                email=email,
                username=username,
                password=DEFAULT_PASSWORD,
                first_name=first,
                last_name=last,
                is_verified=verified,
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Created {created} demo users ({skipped} already existed)"
        ))
        self.stdout.write(f"Password for all: {DEFAULT_PASSWORD}")
        self.stdout.write(f"Verified: {sum(1 for *_, v in DEMO_USERS if v)} / Unverified: {sum(1 for *_, v in DEMO_USERS if not v)}")
