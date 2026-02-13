from django.core.management.base import BaseCommand, CommandError

from apps.tenancy.models import Company
from apps.tenancy.tasks import seed_company_defaults


class Command(BaseCommand):
    help = 'Seed defaults (GHEs, setores, funções, moods, complaints) for one or all companies.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='ID da empresa para seed. Se omitido, roda para todas.',
        )

    def handle(self, *args, **options):
        company_id = options.get('company_id')
        if company_id:
            company = Company.objects.filter(pk=company_id).first()
            if not company:
                raise CommandError('Empresa não encontrada.')
            seed_company_defaults(company.id)
            self.stdout.write(self.style.SUCCESS('Seed concluído para a empresa.'))
            return

        companies = Company.objects.all().only('id')
        if not companies.exists():
            self.stdout.write('Nenhuma empresa encontrada.')
            return

        for company in companies:
            seed_company_defaults(company.id)
        self.stdout.write(self.style.SUCCESS('Seed concluído para todas as empresas.'))
