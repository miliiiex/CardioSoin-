"""Teste la lecture PhysioNet / WFDB sans toucher à la base (hors Django requis)."""

from django.core.management.base import BaseCommand

from cabinet.ecg_analysis import analyze_physionet_mit_record


class Command(BaseCommand):
    help = "Lit un enregistrement MIT-BIH (défaut 100) et affiche l’indice ECG calculé."

    def add_arguments(self, parser):
        parser.add_argument("--record", default="100", help="Identifiant MIT-BIH, ex. 100")
        parser.add_argument(
            "--local-dir",
            default="",
            help="Dossier local contenant les fichiers .hea / .dat / .atr (optionnel).",
        )

    def handle(self, *args, **opts):
        record = (opts.get("record") or "100").strip()
        local = (opts.get("local_dir") or "").strip() or None
        r = analyze_physionet_mit_record(record, local_dir=local)
        if not r.ok:
            self.stderr.write(self.style.ERROR(r.error))
            return
        self.stdout.write(self.style.SUCCESS(f"Enregistrement {record} — OK"))
        self.stdout.write(f"  Durée : {r.duree_s} s, Fs : {r.fs} Hz")
        self.stdout.write(f"  Indice ECG : {r.risk_ecg_seul} %, affiché : {r.risk_percent} % ({r.niveau})")
        self.stdout.write(f"  Points onde (aperçu) : {len(r.waveform)}")
