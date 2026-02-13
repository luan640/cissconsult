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
        mood_labels = [label for label, _, _, _ in DEFAULT_MOOD_TYPES]
        existing_moods = set(
            MoodType.all_objects.filter(company=company, label__in=mood_labels)
            .values_list('label', flat=True)
        )
        mood_to_create = [
            MoodType(
                company=company,
                label=label,
                emoji=emoji,
                sentiment=sentiment,
                mood_score=score,
                is_active=True,
            )
            for label, emoji, sentiment, score in DEFAULT_MOOD_TYPES
            if label not in existing_moods
        ]
        if mood_to_create:
            MoodType.all_objects.bulk_create(mood_to_create)

        existing_complaints = set(
            ComplaintType.all_objects.filter(company=company, label__in=DEFAULT_COMPLAINT_TYPES)
            .values_list('label', flat=True)
        )
        complaints_to_create = [
            ComplaintType(company=company, label=label, is_active=True)
            for label in DEFAULT_COMPLAINT_TYPES
            if label not in existing_complaints
        ]
        if complaints_to_create:
            ComplaintType.all_objects.bulk_create(complaints_to_create)

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

        ghe_names = {ghe_name for ghe_name, _, _ in DEFAULT_GHE_SECTOR_FUNCTIONS}
        ghe_map = {
            ghe.name: ghe
            for ghe in GHE.all_objects.filter(company=company, name__in=ghe_names)
        }
        ghe_to_create = [
            GHE(company=company, name=ghe_name, is_active=True)
            for ghe_name in ghe_names
            if ghe_name not in ghe_map
        ]
        if ghe_to_create:
            GHE.all_objects.bulk_create(ghe_to_create)
            ghe_map = {
                ghe.name: ghe
                for ghe in GHE.all_objects.filter(company=company, name__in=ghe_names)
            }

        department_names = {sector_name for _, sector_name, _ in DEFAULT_GHE_SECTOR_FUNCTIONS}
        department_map = {
            dept.name: dept
            for dept in Department.all_objects.filter(company=company, name__in=department_names)
        }
        departments_to_create = []
        for ghe_name, sector_name, _ in DEFAULT_GHE_SECTOR_FUNCTIONS:
            if sector_name in department_map:
                continue
            ghe_obj = ghe_map.get(ghe_name)
            if ghe_obj is None:
                continue
            departments_to_create.append(
                Department(
                    company=company,
                    name=sector_name,
                    ghe=ghe_obj,
                    is_active=True,
                )
            )
            department_map[sector_name] = None
        if departments_to_create:
            Department.all_objects.bulk_create(departments_to_create)
            department_map = {
                dept.name: dept
                for dept in Department.all_objects.filter(company=company, name__in=department_names)
            }

        departments_to_update = []
        for ghe_name, sector_name, _ in DEFAULT_GHE_SECTOR_FUNCTIONS:
            dept = department_map.get(sector_name)
            if dept and dept.ghe_id is None:
                ghe_obj = ghe_map.get(ghe_name)
                if ghe_obj is not None:
                    dept.ghe = ghe_obj
                    departments_to_update.append(dept)
        if departments_to_update:
            Department.all_objects.bulk_update(departments_to_update, ['ghe', 'updated_at'])

        function_names = {function_name for _, _, function_name in DEFAULT_GHE_SECTOR_FUNCTIONS}
        function_map = {
            jf.name: jf
            for jf in JobFunction.all_objects.filter(company=company, name__in=function_names)
        }
        functions_to_create = [
            JobFunction(company=company, name=function_name, is_active=True)
            for function_name in function_names
            if function_name not in function_map
        ]
        if functions_to_create:
            JobFunction.all_objects.bulk_create(functions_to_create)
            function_map = {
                jf.name: jf
                for jf in JobFunction.all_objects.filter(company=company, name__in=function_names)
            }

        ghe_through = JobFunction.ghes.through
        dept_through = JobFunction.departments.through

        ghe_relations = set()
        dept_relations = set()
        for ghe_name, sector_name, function_name in DEFAULT_GHE_SECTOR_FUNCTIONS:
            ghe_obj = ghe_map.get(ghe_name)
            dept_obj = department_map.get(sector_name)
            func_obj = function_map.get(function_name)
            if not ghe_obj or not dept_obj or not func_obj:
                continue
            ghe_relations.add((func_obj.id, ghe_obj.id))
            dept_relations.add((func_obj.id, dept_obj.id))

        if ghe_relations:
            existing_ghe_relations = set(
                ghe_through.objects.filter(
                    jobfunction_id__in=[pair[0] for pair in ghe_relations],
                    ghe_id__in=[pair[1] for pair in ghe_relations],
                ).values_list('jobfunction_id', 'ghe_id')
            )
            ghe_relations_to_create = [
                ghe_through(jobfunction_id=func_id, ghe_id=ghe_id)
                for func_id, ghe_id in ghe_relations
                if (func_id, ghe_id) not in existing_ghe_relations
            ]
            if ghe_relations_to_create:
                ghe_through.objects.bulk_create(ghe_relations_to_create)

        if dept_relations:
            existing_dept_relations = set(
                dept_through.objects.filter(
                    jobfunction_id__in=[pair[0] for pair in dept_relations],
                    department_id__in=[pair[1] for pair in dept_relations],
                ).values_list('jobfunction_id', 'department_id')
            )
            dept_relations_to_create = [
                dept_through(jobfunction_id=func_id, department_id=dept_id)
                for func_id, dept_id in dept_relations
                if (func_id, dept_id) not in existing_dept_relations
            ]
            if dept_relations_to_create:
                dept_through.objects.bulk_create(dept_relations_to_create)
