from django.db import transaction

from apps.core.models import AlertSetting, ComplaintType, Department, GHE, JobFunction, MoodType
from apps.tenancy.models import Company


DEFAULT_MOOD_TYPES = [
    ('Muito bem', '\U0001F600', 'very_good', 5),
    ('Bem', '\U0001F642', 'good', 4),
    ('Mais ou menos', '\U0001F610', 'neutral', 3),
    ('Normal', '\U0001F60C', 'neutral', 3),
    ('Triste', '\U0001F61F', 'bad', 2),
    ('Irritado', '\U0001F620', 'very_bad', 1),
    ('Sobrecarregado', '\U0001F629', 'bad', 2),
    ('Cansado', '\U0001F62A', 'bad', 2),
    ('Desmotivado', '\U0001F61E', 'bad', 2),
    ('Desapontado', '\U0001F641', 'bad', 2),
    ('Estressado', '\U0001F623', 'very_bad', 1),
]

DEFAULT_COMPLAINT_TYPES = [
    'Assédio moral',
    'Assédio sexual',
    'Discriminação',
    'Conduta antiética',
    'Violência psicológica',
    'Outro',
]

DEFAULT_GHE_SECTOR_FUNCTIONS = [
    ('Administrativo', 'Administrativo Geral', 'Assistente Administrativo'),
    ('Administrativo', 'Financeiro', 'Analista Financeiro'),
    ('Administrativo', 'Contábil', 'Assistente Contábil'),
    ('Administrativo', 'Fiscal', 'Analista Fiscal'),
    ('Administrativo', 'Recursos Humanos', 'Assistente de RH'),
    ('Administrativo', 'Departamento Pessoal', 'Analista de DP'),
    ('Administrativo', 'TI', 'Analista de Sistemas'),
    ('Administrativo', 'TI', 'Suporte Técnico'),
    ('Comercial', 'Vendas Internas', 'Vendedor Interno'),
    ('Comercial', 'Vendas Externas', 'Representante Comercial'),
    ('Comercial', 'Pós-Vendas', 'Analista de Garantia'),
    ('Comercial', 'SAC', 'Assistente de Atendimento'),
    ('Comercial', 'Marketing', 'Analista de Marketing'),
    ('Comercial', 'Licitações', 'Analista de Licitação'),
    ('Produção Industrial', 'Corte', 'Operador de Corte'),
    ('Produção Industrial', 'Serra', 'Operador de Serra'),
    ('Produção Industrial', 'Usinagem', 'Operador de CNC'),
    ('Produção Industrial', 'Usinagem', 'Torneiro Mecânico'),
    ('Produção Industrial', 'Solda', 'Soldador'),
    ('Produção Industrial', 'Pintura', 'Pintor Industrial'),
    ('Produção Industrial', 'Montagem', 'Montador'),
    ('Produção Industrial', 'Estamparia', 'Operador de Prensa'),
    ('Produção Industrial', 'Produção Geral', 'Auxiliar de Produção'),
    ('Logística', 'Almoxarifado', 'Almoxarife'),
    ('Logística', 'Almoxarifado', 'Auxiliar de Almoxarifado'),
    ('Logística', 'Estoque', 'Estoquista'),
    ('Logística', 'Expedição', 'Conferente'),
    ('Logística', 'Expedição', 'Auxiliar de Expedição'),
    ('Logística', 'Recebimento', 'Conferente de Recebimento'),
    ('Logística', 'Transporte', 'Motorista'),
    ('Logística', 'Transporte', 'Ajudante de Entrega'),
    ('Manutenção', 'Manutenção Mecânica', 'Mecânico de Manutenção'),
    ('Manutenção', 'Manutenção Elétrica', 'Eletricista Industrial'),
    ('Manutenção', 'Manutenção Predial', 'Auxiliar de Manutenção'),
    ('Manutenção', 'Manutenção Geral', 'Técnico de Manutenção'),
    ('Engenharia / Técnico', 'Engenharia de Produção', 'Engenheiro de Produção'),
    ('Engenharia / Técnico', 'PCP', 'Analista de PCP'),
    ('Engenharia / Técnico', 'Qualidade', 'Inspetor de Qualidade'),
    ('Engenharia / Técnico', 'Qualidade', 'Analista de Qualidade'),
    ('Engenharia / Técnico', 'Desenvolvimento', 'Projetista'),
    ('Engenharia / Técnico', 'Desenho Técnico', 'Desenhista Mecânico'),
    ('Gestão', 'Produção', 'Supervisor de Produção'),
    ('Gestão', 'Administrativo', 'Coordenador Administrativo'),
    ('Gestão', 'Comercial', 'Gerente Comercial'),
    ('Gestão', 'Industrial', 'Gerente Industrial'),
    ('Gestão', 'Diretoria', 'Diretor Operacional'),
    ('Externo / Campo', 'Assistência Técnica', 'Técnico de Campo'),
    ('Externo / Campo', 'Instalação', 'Instalador'),
    ('Externo / Campo', 'Atendimento Rural', 'Mecânico Externo'),
    ('Externo / Campo', 'Entrega Técnica', 'Técnico de Entrega'),
    ('Segurança do Trabalho', 'SESMT', 'Técnico de Segurança do Trabalho'),
    ('Segurança do Trabalho', 'SESMT', 'Engenheiro de Segurança'),
    ('Segurança do Trabalho', 'SESMT', 'Auxiliar de Segurança'),
]


def seed_company_defaults(company_id: int) -> None:
    company = Company.objects.filter(pk=company_id).first()
    if not company:
        return

    with transaction.atomic():
        for label, emoji, sentiment, score in DEFAULT_MOOD_TYPES:
            MoodType.all_objects.get_or_create(
                company=company,
                label=label,
                defaults={
                    'emoji': emoji,
                    'sentiment': sentiment,
                    'mood_score': score,
                    'is_active': True,
                },
            )

        for label in DEFAULT_COMPLAINT_TYPES:
            ComplaintType.all_objects.get_or_create(
                company=company,
                label=label,
                defaults={
                    'is_active': True,
                },
            )

        AlertSetting.all_objects.get_or_create(
            company=company,
            defaults={
                'auto_alerts_enabled': True,
                'analysis_window_days': 30,
                'max_critical_complaints': 5,
                'max_negative_mood_percent': 35,
                'max_open_help_requests': 10,
                'is_active': True,
            },
        )

        ghe_cache = {}
        department_cache = {}

        for ghe_name, sector_name, function_name in DEFAULT_GHE_SECTOR_FUNCTIONS:
            ghe_obj = ghe_cache.get(ghe_name)
            if ghe_obj is None:
                ghe_obj, _ = GHE.all_objects.get_or_create(
                    company=company,
                    name=ghe_name,
                    defaults={'is_active': True},
                )
                ghe_cache[ghe_name] = ghe_obj

            department_obj = department_cache.get(sector_name)
            if department_obj is None:
                department_obj, created_department = Department.all_objects.get_or_create(
                    company=company,
                    name=sector_name,
                    defaults={
                        'ghe': ghe_obj,
                        'is_active': True,
                    },
                )
                if not created_department and department_obj.ghe_id is None:
                    department_obj.ghe = ghe_obj
                    department_obj.save(update_fields=['ghe', 'updated_at'])
                department_cache[sector_name] = department_obj

            job_function, _ = JobFunction.all_objects.get_or_create(
                company=company,
                name=function_name,
                defaults={'is_active': True},
            )
            job_function.ghes.add(ghe_obj)
            job_function.departments.add(department_obj)
