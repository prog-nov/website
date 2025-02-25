from io import StringIO

from django.http import HttpResponse

from . import export_zip, clean_filename


def write_vcard(data, file):
    for user in data:

        card = "BEGIN:VCARD\n"
        card += "VERSION:3.0\n"
        card += f"EMAIL:{user.email}\n"
        card += f"FN:{user.first_name} {user.last_name}\n"
        card += f"GENDER:{user.profile.gender or ''}\n"
        card += f"N:{user.last_name};{user.first_name};;;\n"
        if user.profile.phone_number:
            tel = user.profile.phone_number
            if len(tel) >= 2 and tel[0:2] == "07":  # Add country code for swiss numbers
                tel = "+41 " + tel[1:]
            card += "TEL:{}\n".format(tel)
        card += "END:VCARD\n"

        file.write(card)


def export_vcard(title, data, multiple=False):

    if multiple:
        files = dict()
        for count, item in enumerate(data):
            file = StringIO()
            write_vcard(item['data'], file)
            files["{}_{}.vcf".format(count + 1, item['name'])] = file.getvalue()

        return export_zip(title, files)

    else:
        response = HttpResponse(content_type='text/vcard')
        response['Content-Disposition'] = 'attachment; filename="{}.vcf"'.format(clean_filename(title))
        write_vcard(data, response)
        return response