#! /usr/bin/python3
# -*- coding:utf-8 -*-

# pamac - A Python implementation of alpm
# Copyright (C) 2013-2014  Guillaume Benoit <guillaume@manjaro.org>
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

version = '0.9.8'

from gi.repository import Gtk, Gdk
import pyalpm
import dbus
from time import strftime, localtime

from pamac import config, common, transaction, aur

# i18n
import gettext
import locale
locale.bindtextdomain('pamac', '/usr/share/locale')
gettext.bindtextdomain('pamac', '/usr/share/locale')
gettext.textdomain('pamac')
_ = gettext.gettext

interface = transaction.interface

interface.add_from_file('/usr/share/pamac/gui/manager.ui')
ManagerWindow = interface.get_object("ManagerWindow")
deps_list = interface.get_object('deps_list')
details_list = interface.get_object('details_list')
files_textview = interface.get_object('files_textview')
deps_scrolledwindow = interface.get_object('deps_scrolledwindow')
files_scrolledwindow = interface.get_object('files_scrolledwindow')
details_scrolledwindow = interface.get_object('details_scrolledwindow')
name_label = interface.get_object('name_label')
desc_label = interface.get_object('desc_label')
link_label = interface.get_object('link_label')
pkg_link_label = interface.get_object('pkg_link_label')
licenses_label = interface.get_object('licenses_label')
search_entry = interface.get_object('search_entry')
search_aur_button = interface.get_object('search_aur_button')
search_list = interface.get_object('search_list')
search_selection = interface.get_object('search_treeview_selection')
packages_list_treeview = interface.get_object('packages_list_treeview')
state_column = interface.get_object('state_column')
name_column = interface.get_object('name_column')
version_column = interface.get_object('version_column')
repo_column = interface.get_object('repo_column')
size_column = interface.get_object('size_column')
state_rendererpixbuf = interface.get_object('state_rendererpixbuf')
name_renderertext = interface.get_object('name_renderertext')
version_renderertext = interface.get_object('version_renderertext')
repo_renderertext = interface.get_object('repo_renderertext')
size_renderertext = interface.get_object('size_renderertext')
list_selection = interface.get_object('list_treeview_selection')
groups_list = interface.get_object('groups_list')
groups_selection = interface.get_object('groups_treeview_selection')
states_list = interface.get_object('states_list')
states_selection = interface.get_object('states_treeview_selection')
repos_list = interface.get_object('repos_list')
repos_selection = interface.get_object('repos_treeview_selection')
AboutDialog = interface.get_object('AboutDialog')
PackagesChooserDialog = interface.get_object('PackagesChooserDialog')
HistoryWindow = interface.get_object('HistoryWindow')
history_textview = interface.get_object('history_textview')
ManagerValidButton = interface.get_object('ManagerValidButton')
ManagerCancelButton = interface.get_object('ManagerCancelButton')

files_buffer = files_textview.get_buffer()
history_buffer = history_textview.get_buffer()
AboutDialog.set_version(version)
search_aur_button.set_visible(config.enable_aur)
ManagerValidButton.set_sensitive(False)
ManagerCancelButton.set_sensitive(False)

search_dict = {}
groups_dict = {}
states_dict = {}
repos_dict = {}
current_filter = (None, None)
right_click_menu = Gtk.Menu()

installed_icon = Gtk.IconTheme.get_default().load_icon('package-installed-updated', 16, 0)
uninstalled_icon = Gtk.IconTheme.get_default().load_icon('package-available', 16, 0)
to_install_icon = Gtk.IconTheme.get_default().load_icon('package-install', 16, 0)
to_reinstall_icon = Gtk.IconTheme.get_default().load_icon('package-reinstall', 16, 0)
to_remove_icon = Gtk.IconTheme.get_default().load_icon('package-remove', 16, 0)
locked_icon = Gtk.IconTheme.get_default().load_icon('package-installed-locked', 16, 0)

def state_column_display_func(column, cell, treemodel, treeiter, data):
	if treemodel[treeiter][0] == _('No package found'):
		pixbuf = None
	elif treemodel[treeiter][0].name in config.holdpkg:
		pixbuf = locked_icon
	elif treemodel[treeiter][0].db.name == 'local':
		if treemodel[treeiter][0].name in transaction.to_add:
			pixbuf = to_reinstall_icon
		elif treemodel[treeiter][0].name in transaction.to_remove:
			pixbuf = to_remove_icon
		else:
			pixbuf = installed_icon
	elif treemodel[treeiter][0].name in transaction.to_add:
		pixbuf = to_install_icon
	elif treemodel[treeiter][0] in transaction.to_build:
		pixbuf = to_install_icon
	else:
		pixbuf = uninstalled_icon
	cell.set_property("pixbuf", pixbuf)

def state_column_sort_func(treemodel, treeiter1, treeiter2, data):
	if treemodel[treeiter1][0].db.name == 'local':
		num1 = 1
	else:
		num1 = 0
	if treemodel[treeiter2][0].db.name == 'local':
		num2 = 1
	else:
		num2 = 0
	return num1 - num2

def name_column_display_func(column, cell, treemodel, treeiter, data):
	if treemodel[treeiter][0] == _('No package found'):
		cell.set_property("text", _('No package found'))
	else:
		cell.set_property("text", treemodel[treeiter][0].name)

def name_column_sort_func(treemodel, treeiter1, treeiter2, data):
	str1 = treemodel[treeiter1][0].name
	str2 = treemodel[treeiter2][0].name
	if str1 < str2:
		return -1
	elif str1 > str2:
		return 1
	else:
		return 0

def version_column_display_func(column, cell, treemodel, treeiter, data):
	if treemodel[treeiter][0] == _('No package found'):
		cell.set_property("text", '')
	else:
		cell.set_property("text", treemodel[treeiter][0].version)

def version_column_sort_func(treemodel, treeiter1, treeiter2, data):
	return pyalpm.vercmp(treemodel[treeiter1][0].version, treemodel[treeiter2][0].version)

def repo_column_display_func(column, cell, treemodel, treeiter, data):
	if treemodel[treeiter][0] == _('No package found'):
		cell.set_property("text", '')
	else:
		cell.set_property("text", treemodel[treeiter][0].db.name)

def repo_column_sort_func(treemodel, treeiter1, treeiter2, data):
	servers = list(config.pacman_conf.repos.keys())
	servers.insert(0, 'local')
	# display AUR at last
	if treemodel[treeiter1][0].db.name == 'AUR':
		num1 = 99
	else:
		num1 = servers.index(treemodel[treeiter1][0].db.name)
	# display AUR at last
	if treemodel[treeiter2][0].db.name == 'AUR':
		num2 = 99
	else:
		num2 = servers.index(treemodel[treeiter2][0].db.name)
	return num1 - num2

def size_column_display_func(column, cell, treemodel, treeiter, data):
	if treemodel[treeiter][0] == _('No package found'):
		cell.set_property("text", '')
	elif treemodel[treeiter][0].isize:
		cell.set_property("text", common.format_size(treemodel[treeiter][0].isize))
	else:
		cell.set_property("text", '')

def size_column_sort_func(treemodel, treeiter1, treeiter2, data):
	if treemodel[treeiter1][0].isize:
		num1 = treemodel[treeiter1][0].isize
	else:
		num1 = 0
	if treemodel[treeiter2][0].isize:
		num2 = treemodel[treeiter2][0].isize
	else:
		num2 = 0
	return num1 - num2

def update_lists():
	grps_set = set()
	for db in transaction.syncdbs:
		repos_list.append([db.name])
		for name, pkgs in db.grpcache:
			grps_set.add(name)
	repos_list.append([_('local')])
	for name in grps_set:
		groups_list.append([name])
	groups_list.set_sort_column_id(0, Gtk.SortType.ASCENDING)
	states = [_('Installed'), _('Uninstalled'), _('Orphans'), _('To install'), _('To remove')]
	for state in states:
		states_list.append([state])

def get_group_list(group):
	global groups_dict
	if group in groups_dict.keys():
		return groups_dict[group]
	else:
		groups_dict[group] = Gtk.ListStore(object)
		dbs_list = [transaction.localdb]
		dbs_list.extend(transaction.syncdbs.copy())
		pkgs = pyalpm.find_grp_pkgs(dbs_list, group)
		for pkg in pkgs:
			groups_dict[group].append([pkg])
		return groups_dict[group]

def get_state_list(state):
	global states_dict
	if state == _('To install'):
		liststore = Gtk.ListStore(object)
		for name in transaction.to_add:
			pkg = transaction.get_localpkg(name)
			if pkg:
				liststore.append([pkg])
			else:
				pkg = transaction.get_syncpkg(name)
				if pkg:
					liststore.append([pkg])
		return liststore
	elif state == _('To remove'):
		liststore = Gtk.ListStore(object)
		for name in transaction.to_remove:
			pkg = transaction.get_localpkg(name)
			if pkg:
				liststore.append([pkg])
		return liststore
	elif state in states_dict.keys():
		return states_dict[state]
	else:
		states_dict[state] = Gtk.ListStore(object)
		if state == _('Installed'):
			for pkg in transaction.localdb.pkgcache:
				states_dict[state].append([pkg])
		elif state == _('Uninstalled'):
			for pkg in get_uninstalled_pkgs():
				states_dict[state].append([pkg])
		elif state == _('Orphans'):
			for pkg in get_orphan_pkgs():
				states_dict[state].append([pkg])
		return states_dict[state]

def get_repo_list(repo):
	global repos_dict
	if repo in repos_dict.keys():
		return repos_dict[repo]
	else:
		repos_dict[repo] = Gtk.ListStore(object)
		if repo == _('local'):
			for pkg in transaction.localdb.pkgcache:
				if not transaction.get_syncpkg(pkg.name):
					repos_dict[repo].append([pkg])
		else:
			for db in transaction.syncdbs:
				if db.name ==repo:
					for pkg in db.pkgcache:
						local_pkg = transaction.get_localpkg(pkg.name)
						if local_pkg:
							repos_dict[repo].append([local_pkg])
						else:
							repos_dict[repo].append([pkg])
		return repos_dict[repo]

def search_pkgs(data_tupel):
	global search_dict
	search_string = data_tupel[0]
	search_aur = data_tupel[1]
	if (search_string, search_aur) in search_dict.keys():
		return search_dict[(search_string, search_aur)]
	else:
		search_dict[(search_string, search_aur)] = Gtk.ListStore(object)
		names_list = []
		for pkg in transaction.localdb.search(*search_string.split()):
			if not pkg.name in names_list:
				names_list.append(pkg.name)
				search_dict[(search_string, search_aur)].append([pkg])
		for db in transaction.syncdbs:
			for pkg in db.search(*search_string.split()):
				if not pkg.name in names_list:
					names_list.append(pkg.name)
					search_dict[(search_string, search_aur)].append([pkg])
		if search_aur:
			for pkg in aur.search(*search_string.split()):
				if not pkg.name in names_list:
					names_list.append(pkg.name)
					search_dict[(search_string, search_aur)].append([pkg])
		if not names_list:
			search_dict[(search_string, search_aur)].append([_('No package found')])
		else:
			if not search_string in [row[0] for row in search_list]:
				search_list.append([search_string])
		return search_dict[(search_string, search_aur)] 

def get_uninstalled_pkgs():
	pkgs_list = []
	names_list = []
	for repo in transaction.syncdbs:
		for pkg in repo.pkgcache:
			if not pkg.name in names_list:
				names_list.append(pkg.name)
				if not transaction.get_localpkg(pkg.name):
					pkgs_list.append(pkg)
	return pkgs_list

def get_orphan_pkgs():
	pkgs_list = []
	for pkg in transaction.localdb.pkgcache:
		if pkg.reason == pyalpm.PKG_REASON_DEPEND:
			if not pkg.compute_requiredby():
				pkgs_list.append(pkg)
	return pkgs_list

def refresh_packages_list(liststore):
	packages_list_treeview.freeze_child_notify()
	packages_list_treeview.set_model(None)
	liststore.set_sort_func(0, name_column_sort_func, None)
	liststore.set_sort_column_id(0, Gtk.SortType.ASCENDING)
	packages_list_treeview.set_model(liststore)
	state_column.set_sort_indicator(False)
	name_column.set_sort_indicator(True)
	version_column.set_sort_indicator(False)
	repo_column.set_sort_indicator(False)
	size_column.set_sort_indicator(False)
	packages_list_treeview.thaw_child_notify()
	# clear infos tabs
	name_label.set_markup('')
	desc_label.set_markup('')
	link_label.set_markup('')
	pkg_link_label.set_markup('')
	licenses_label.set_markup('')
	deps_list.clear()
	details_list.clear()
	files_buffer.delete(files_buffer.get_start_iter(), files_buffer.get_end_iter())
	ManagerWindow.get_window().set_cursor(None)

def set_infos_list(pkg):
	if pkg.db.name == 'AUR':
		pkg_url = 'https://aur.archlinux.org/packages/{}/'.format(pkg.name)
	elif pkg.db.name == 'local':
		# We don't know the db name, so we can't determine the url
		pkg_url = ''
	else:
		pkg_url = 'https://www.archlinux.org/packages/{0.db.name}/{0.arch}/{0.name}/'.format(pkg)

	name_label.set_markup('<big><b>{}  {}</b></big>'.format(pkg.name, pkg.version))
	# fix &,-,>,< in desc
	desc = pkg.desc.replace('&', '&amp;')
	desc = desc.replace('<->', '/')
	desc_label.set_markup(desc)
	# fix & in url
	url = pkg.url.replace('&', '&amp;')
	link_label.set_markup('<a href=\"{_url}\">{_url}</a>'.format(_url = url))
	licenses_label.set_markup(_('Licenses')+': {}'.format(' '.join(pkg.licenses)))
	if pkg_url:
		pkg_link_label.set_markup('Package: <a href=\"{_url}\">{_url}</a>'.format(_url = pkg_url))
	else:
		pkg_link_label.set_markup('')

def set_deps_list(pkg, style):
	deps_list.clear()
	if pkg.depends:
		deps_list.append([_('Depends On')+':', '\n'.join(pkg.depends)])
	if pkg.optdepends:
		optdeps = []
		for optdep in pkg.optdepends:
			if pyalpm.find_satisfier(transaction.localdb.pkgcache, optdep.split(':')[0]):
				optdeps.append(optdep+' ['+_('Installed')+']')
			else:
				optdeps.append(optdep)
		deps_list.append([_('Optional Deps')+':', '\n'.join(optdeps)])
	if style == 'local':
		if pkg.compute_requiredby():
			deps_list.append([_('Required By')+':', '\n'.join(pkg.compute_requiredby())])
	if pkg.provides:
		deps_list.append([_('Provides')+':', '\n'.join(pkg.provides)])
	if pkg.replaces:
		deps_list.append([_('Replaces')+':', '\n'.join(pkg.replaces)])
	if pkg.conflicts:
		deps_list.append([_('Conflicts With')+':', '\n'.join(pkg.conflicts)])

def set_details_list(pkg, style):
	details_list.clear()
	if style == 'sync':
		details_list.append([_('Repository')+':', pkg.db.name])
	if pkg.groups:
		details_list.append([_('Groups')+':', ' '.join(pkg.groups)])
	if style == 'sync':
		details_list.append([_('Compressed Size')+':', common.format_size(pkg.size)])
		details_list.append([_('Download Size')+':', common.format_size(pkg.download_size)])
	if style == 'local':
		details_list.append([_('Installed Size')+':', common.format_size(pkg.isize)])
	details_list.append([_('Packager')+':', pkg.packager])
	details_list.append([_('Architecture')+':', pkg.arch])
	#details_list.append([_('Build Date')+':', strftime("%a %d %b %Y %X %Z", localtime(pkg.builddate))])
	if style == 'local':
		details_list.append([_('Install Date')+':', strftime("%a %d %b %Y %X %Z", localtime(pkg.installdate))])
		if pkg.reason == pyalpm.PKG_REASON_EXPLICIT:
			reason = _('Explicitly installed')
		elif pkg.reason == pyalpm.PKG_REASON_DEPEND:
			reason = _('Installed as a dependency for another package')
		else:
			reason = _('Unknown')
		details_list.append([_('Install Reason')+':', reason])
	if style == 'sync':
		#details_list.append([_('Install Script')':', 'Yes' if pkg.has_scriptlet else 'No'])
		#details_list.append(['MD5 Sum:', pkg.md5sum])
		#details_list.append(['SHA256 Sum:', pkg.sha256sum])
		details_list.append([_('Signatures')+':', 'Yes' if pkg.base64_sig else 'No'])
	if style == 'local':
		if len(pkg.backup) != 0:
			#details_list.append(['_(Backup files)+':', '\n'.join(["%s %s" % (md5, file) for (file, md5) in pkg.backup])])
			details_list.append([_('Backup files')+':', '\n'.join(["%s" % (file) for (file, md5) in pkg.backup])])

def set_files_list(pkg):
	files_buffer.delete(files_buffer.get_start_iter(), files_buffer.get_end_iter())
	if len(pkg.files) != 0:
		for file in pkg.files:
			end_iter = files_buffer.get_end_iter()
			files_buffer.insert(end_iter, '/'+file[0]+'\n')

def handle_error(error):
	ManagerWindow.get_window().set_cursor(None)
	while Gtk.events_pending():
		Gtk.main_iteration()
	if error:
		if not 'DBus.Error.NoReply' in str(error):
			print(error)
			transaction.ErrorDialog.format_secondary_text(str(error))
			response = transaction.ErrorDialog.run()
			if response:
				transaction.ErrorDialog.hide()
				transaction.ProgressWindow.hide()
	transaction.progress_buffer.delete(transaction.progress_buffer.get_start_iter(),transaction.progress_buffer.get_end_iter())
	transaction.Release()
	transaction.get_handle()
	transaction.mark_needed_pkgs_as_dep()
	transaction.to_add.clear()
	transaction.to_remove.clear()
	transaction.to_update.clear()
	transaction.to_load.clear()
	transaction.to_build.clear()
	ManagerValidButton.set_sensitive(False)
	ManagerCancelButton.set_sensitive(False)

def handle_reply(reply):
	if transaction.to_build:
		transaction.build_next() 
	elif reply:
		transaction.ProgressCloseButton.set_visible(True)
		transaction.action_icon.set_from_icon_name('dialog-information', Gtk.IconSize.BUTTON)
		transaction.progress_label.set_text(str(reply))
		transaction.progress_bar.set_text('')
		end_iter = transaction.progress_buffer.get_end_iter()
		transaction.progress_buffer.insert(end_iter, str(reply))
	else:
		transaction.get_updates()
	transaction.Release()
	transaction.get_handle()
	transaction.mark_needed_pkgs_as_dep()
	transaction.to_add.clear()
	transaction.to_remove.clear()
	transaction.to_update.clear()
	transaction.to_load.clear()
	ManagerValidButton.set_sensitive(False)
	ManagerCancelButton.set_sensitive(False)
	global search_dict
	global groups_dict
	global states_dict
	global repos_dict
	search_dict = {}
	groups_dict = {}
	states_dict = {}
	repos_dict = {}
	if current_filter[0]:
		refresh_packages_list(current_filter[0](current_filter[1]))

def handle_updates(updates):
	ManagerWindow.get_window().set_cursor(None)
	transaction.ProgressWindow.hide()
	transaction.available_updates = updates
	error = transaction.sysupgrade()
	if error:
		handle_error(error)

def reload_config(msg):
	config.pamac_conf.reload()
	if config.enable_aur == False:
		search_aur_button.set_active(False)
	search_aur_button.set_visible(config.enable_aur)
	#transaction.get_updates()

def on_ManagerWindow_delete_event(*args):
	transaction.StopDaemon()
	common.rm_pid_file()
	Gtk.main_quit()

def on_TransValidButton_clicked(*args):
	transaction.ConfDialog.hide()
	while Gtk.events_pending():
		Gtk.main_iteration()
	transaction.finalize()

def on_TransCancelButton_clicked(*args):
	transaction.ProgressWindow.hide()
	transaction.progress_buffer.delete(transaction.progress_buffer.get_start_iter(),transaction.progress_buffer.get_end_iter())
	transaction.ConfDialog.hide()
	while Gtk.events_pending():
		Gtk.main_iteration()
	transaction.Release()
	transaction.to_add.clear()
	transaction.to_remove.clear()
	transaction.to_update.clear()
	transaction.to_load.clear()
	transaction.to_build.clear()
	ManagerValidButton.set_sensitive(False)
	ManagerCancelButton.set_sensitive(False)
	if current_filter[0]:
		refresh_packages_list(current_filter[0](current_filter[1]))

def on_ProgressCloseButton_clicked(*args):
	transaction.progress_buffer.delete(transaction.progress_buffer.get_start_iter(),transaction.progress_buffer.get_end_iter())
	transaction.need_details_handler(False)
	transaction.to_build.clear()
	#ManagerWindow.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
	#while Gtk.events_pending():
		#Gtk.main_iteration()
	#transaction.get_updates()
	ManagerWindow.get_window().set_cursor(None)
	transaction.ProgressWindow.hide()

def on_ProgressCancelButton_clicked(*args):
	ManagerWindow.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
	while Gtk.events_pending():
		Gtk.main_iteration()
	transaction.progress_buffer.delete(transaction.progress_buffer.get_start_iter(),transaction.progress_buffer.get_end_iter())
	transaction.cancel_download = True
	if transaction.build_proc:
		if transaction.build_proc.poll() is None:
			transaction.build_proc.kill()
			transaction.build_proc.wait()
	transaction.to_add.clear()
	transaction.to_remove.clear()
	transaction.to_update.clear()
	transaction.to_load.clear()
	transaction.to_build.clear()
	ManagerValidButton.set_sensitive(False)
	ManagerCancelButton.set_sensitive(False)
	transaction.Interrupt()
	ManagerWindow.get_window().set_cursor(None)
	transaction.ProgressWindow.hide()
	while Gtk.events_pending():
		Gtk.main_iteration()

def on_search_entry_icon_press(*args):
	on_search_entry_activate(None)

def on_search_entry_activate(widget):
	global current_filter
	ManagerWindow.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
	while Gtk.events_pending():
		Gtk.main_iteration()
	current_filter = (search_pkgs, (search_entry.get_text(), search_aur_button.get_active()))
	refresh_packages_list(search_pkgs((search_entry.get_text(), search_aur_button.get_active())))

def mark_to_install(widget, pkg):
	if pkg.db.name == 'AUR':
		transaction.to_build.append(pkg)
	else:
		transaction.to_add.add(pkg.name)
	ManagerValidButton.set_sensitive(True)
	ManagerCancelButton.set_sensitive(True)

def mark_to_reinstall(widget, pkg):
	transaction.to_add.add(pkg.name)
	ManagerValidButton.set_sensitive(True)
	ManagerCancelButton.set_sensitive(True)

def mark_to_remove(widget, pkg):
	transaction.to_remove.add(pkg.name)
	ManagerValidButton.set_sensitive(True)
	ManagerCancelButton.set_sensitive(True)

def mark_to_deselect(widget, pkg):
	transaction.to_remove.discard(pkg.name)
	transaction.to_add.discard(pkg.name)
	if pkg in transaction.to_build:
		transaction.to_build.remove(pkg)
	if not transaction.to_add and not transaction.to_remove and not transaction.to_build:
		ManagerValidButton.set_sensitive(False)
		ManagerCancelButton.set_sensitive(False)

def select_optdeps(widget, pkg, optdeps):
	transaction.choose_label.set_markup('<b>{}</b>'.format(_('{pkgname} has {number} uninstalled optional deps.\nPlease choose those you would like to install:').format(pkgname = pkg.name, number = str(len(optdeps)))))
	transaction.choose_list.clear()
	for long_string in optdeps:
		transaction.choose_list.append([False, long_string])
	transaction.ChooseDialog.run()
	# some optdep can be virtual package so check for providers
	for name in transaction.to_add:
		if not transaction.get_syncpkg(name):
			transaction.to_add.discard(name)
			# if a provider is already installed, do nothing
			if pyalpm.find_satisfier(transaction.localdb.pkgcache, name):
				continue
			providers = set()
			for db in transaction.syncdbs:
				pkgs = db.pkgcache
				provider = pyalpm.find_satisfier(pkgs, name)
				while provider:
					providers.add(provider.name)
					for pkg in pkgs:
						if pkg.name == provider.name:
							pkgs.remove(pkg)
							break
					provider = pyalpm.find_satisfier(pkgs, name)
			transaction.choose_provides((providers, name))
	if transaction.to_add:
		ManagerValidButton.set_sensitive(True)
		ManagerCancelButton.set_sensitive(True)

def install_with_optdeps(widget, pkg, optdeps):
	select_optdeps(widget, pkg, optdeps)
	transaction.to_add.add(pkg.name)
	ManagerValidButton.set_sensitive(True)
	ManagerCancelButton.set_sensitive(True)

def mark_explicitly_installed(widget, pkg):
	error = transaction.SetPkgReason(pkg.name, pyalpm.PKG_REASON_EXPLICIT)
	if error:
		handle_error(error)
	transaction.get_handle()
	global search_dict
	global groups_dict
	global states_dict
	global repos_dict
	search_dict = {}
	groups_dict = {}
	states_dict = {}
	repos_dict = {}
	if current_filter[0]:
		refresh_packages_list(current_filter[0](current_filter[1]))

def on_list_treeview_button_press_event(treeview, event):
	global right_click_menu
	liststore = packages_list_treeview.get_model()
	# Check if right mouse button was clicked
	if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
		while Gtk.events_pending():
			Gtk.main_iteration()
		treepath, viewcolumn, x, y = treeview.get_path_at_pos(int(event.x), int(event.y))
		treeiter = liststore.get_iter(treepath)
		if treeiter:
			if liststore[treeiter][0] != _('No package found') and not liststore[treeiter][0].name in config.holdpkg:
				right_click_menu = Gtk.Menu()
				if liststore[treeiter][0].name in transaction.to_add | transaction.to_remove or liststore[treeiter][0] in transaction.to_build:
					item = Gtk.ImageMenuItem(_('Deselect'))
					item.set_image(Gtk.Image.new_from_stock('gtk-undo', Gtk.IconSize.MENU))
					item.connect('activate', mark_to_deselect, liststore[treeiter][0])
					right_click_menu.append(item)
				elif liststore[treeiter][0].db.name == 'local':
					item = Gtk.ImageMenuItem(_('Remove'))
					item.set_image(Gtk.Image.new_from_pixbuf(to_remove_icon))
					item.connect('activate', mark_to_remove, liststore[treeiter][0])
					right_click_menu.append(item)
					if transaction.get_syncpkg(liststore[treeiter][0].name):
						if not pyalpm.sync_newversion(liststore[treeiter][0], transaction.syncdbs):
							item = Gtk.ImageMenuItem(_('Reinstall'))
							item.set_image(Gtk.Image.new_from_pixbuf(to_reinstall_icon))
							item.connect('activate', mark_to_reinstall, liststore[treeiter][0])
							right_click_menu.append(item)
					optdeps_strings = liststore[treeiter][0].optdepends
					if optdeps_strings:
						available_optdeps = []
						for optdep_string in optdeps_strings:
							if not pyalpm.find_satisfier(transaction.localdb.pkgcache, optdep_string.split(':')[0]):
								available_optdeps.append(optdep_string)
						if available_optdeps:
							item = Gtk.ImageMenuItem(_('Install optional deps'))
							item.set_image(Gtk.Image.new_from_pixbuf(to_install_icon))
							item.connect('activate', select_optdeps, liststore[treeiter][0], available_optdeps)
							right_click_menu.append(item)
					if liststore[treeiter][0].reason == pyalpm.PKG_REASON_DEPEND:
						item = Gtk.MenuItem(_('Mark as explicitly installed'))
						item.connect('activate', mark_explicitly_installed, liststore[treeiter][0])
						right_click_menu.append(item)
				else:
					item = Gtk.ImageMenuItem(_('Install'))
					item.set_image(Gtk.Image.new_from_pixbuf(to_install_icon))
					item.connect('activate', mark_to_install, liststore[treeiter][0])
					right_click_menu.append(item)
					optdeps_strings = liststore[treeiter][0].optdepends
					if optdeps_strings:
						available_optdeps = []
						for optdep_string in optdeps_strings:
							if not pyalpm.find_satisfier(transaction.localdb.pkgcache, optdep_string.split(':')[0]):
								available_optdeps.append(optdep_string)
						if available_optdeps:
							item = Gtk.ImageMenuItem(_('Install with optional deps'))
							item.set_image(Gtk.Image.new_from_pixbuf(to_install_icon))
							item.connect('activate', install_with_optdeps, liststore[treeiter][0], available_optdeps)
							right_click_menu.append(item)
				treeview.grab_focus()
				treeview.set_cursor(treepath, viewcolumn, 0)
				right_click_menu.show_all()
				right_click_menu.popup(None, None, None, None, event.button, event.time)
				return True

def on_list_treeview_selection_changed(treeview):
	liststore, treeiter = list_selection.get_selected()
	if treeiter:
		if liststore[treeiter][0] != _('No package found'):
			set_infos_list(liststore[treeiter][0])
			if liststore[treeiter][0].db.name == 'local':
				set_deps_list(liststore[treeiter][0], "local")
				set_details_list(liststore[treeiter][0], "local")
				set_files_list(liststore[treeiter][0])
				deps_scrolledwindow.set_visible(True)
				details_scrolledwindow.set_visible(True)
				files_scrolledwindow.set_visible(True)
			elif liststore[treeiter][0].db.name == 'AUR':
				deps_scrolledwindow.set_visible(False)
				details_scrolledwindow.set_visible(False)
				files_scrolledwindow.set_visible(False)
			else:
				set_deps_list(liststore[treeiter][0], "sync")
				set_details_list(liststore[treeiter][0], "sync")
				deps_scrolledwindow.set_visible(True)
				details_scrolledwindow.set_visible(True)
				files_scrolledwindow.set_visible(False)

def on_search_treeview_selection_changed(widget):
	global current_filter
	while Gtk.events_pending():
		Gtk.main_iteration()
	liste, line = search_selection.get_selected()
	if line:
		ManagerWindow.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
		while Gtk.events_pending():
			Gtk.main_iteration()
		current_filter = (search_pkgs, (search_list[line][0], search_aur_button.get_active()))
		refresh_packages_list(search_pkgs((search_list[line][0], search_aur_button.get_active())))

def on_groups_treeview_selection_changed(widget):
	global current_filter
	while Gtk.events_pending():
		Gtk.main_iteration()
	liste, line = groups_selection.get_selected()
	if line:
		ManagerWindow.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
		while Gtk.events_pending():
			Gtk.main_iteration()
		current_filter = (get_group_list, groups_list[line][0])
		refresh_packages_list(get_group_list(groups_list[line][0]))

def on_states_treeview_selection_changed(widget):
	global current_filter
	while Gtk.events_pending():
		Gtk.main_iteration()
	liste, line = states_selection.get_selected()
	if line:
		ManagerWindow.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
		while Gtk.events_pending():
			Gtk.main_iteration()
		current_filter = (get_state_list, states_list[line][0])
		refresh_packages_list(get_state_list(states_list[line][0]))

def on_repos_treeview_selection_changed(widget):
	global current_filter
	while Gtk.events_pending():
		Gtk.main_iteration()
	liste, line = repos_selection.get_selected()
	if line:
		ManagerWindow.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
		while Gtk.events_pending():
			Gtk.main_iteration()
		current_filter = (get_repo_list, repos_list[line][0])
		refresh_packages_list(get_repo_list(repos_list[line][0]))

def on_list_treeview_row_activated(treeview, treeiter, column):
	liststore = treeview.get_model()
	if not liststore[treeiter][0] == _('No package found'):
		if liststore[treeiter][0].name in transaction.to_add:
			transaction.to_add.discard(liststore[treeiter][0].name)
		elif liststore[treeiter][0] in transaction.to_build:
			transaction.to_build.remove(liststore[treeiter][0])
		elif liststore[treeiter][0].name in transaction.to_remove:
			transaction.to_remove.discard(liststore[treeiter][0].name)
		elif liststore[treeiter][0].db.name == 'local':
			if not liststore[treeiter][0].name in config.holdpkg:
				transaction.to_remove.add(liststore[treeiter][0].name)
		elif liststore[treeiter][0].db.name == 'AUR':
			transaction.to_build.append(liststore[treeiter][0])
		else:
			transaction.to_add.add(liststore[treeiter][0].name)
		if transaction.to_add or transaction.to_remove or transaction.to_build:
			ManagerValidButton.set_sensitive(True)
			ManagerCancelButton.set_sensitive(True)
		elif not transaction.to_add and not transaction.to_remove and not transaction.to_build:
			ManagerValidButton.set_sensitive(False)
			ManagerCancelButton.set_sensitive(False)
	while Gtk.events_pending():
		Gtk.main_iteration()

def on_notebook1_switch_page(notebook, page, page_num):
	ManagerWindow.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
	while Gtk.events_pending():
		Gtk.main_iteration()
	if page_num == 0:
		liste, line = search_selection.get_selected()
		if line:
			on_search_treeview_selection_changed(None)
		elif search_entry.get_text():
			on_search_entry_activate(None)
		else:
			ManagerWindow.get_window().set_cursor(None)
	elif page_num == 1:
		on_groups_treeview_selection_changed(None)
	elif page_num == 2:
		on_states_treeview_selection_changed(None)
	elif page_num == 3:
		on_repos_treeview_selection_changed(None)

def on_ManagerValidButton_clicked(*args):
	ManagerWindow.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
	while Gtk.events_pending():
		Gtk.main_iteration()
	error = transaction.run(recurse = config.recurse)
	ManagerWindow.get_window().set_cursor(None)
	if error:
		handle_error(error)

def on_ManagerCancelButton_clicked(*args):
	transaction.to_add.clear()
	transaction.to_remove.clear()
	transaction.to_update.clear()
	transaction.to_load.clear()
	transaction.to_build.clear()
	ManagerValidButton.set_sensitive(False)
	ManagerCancelButton.set_sensitive(False)
	if current_filter[0]:
		refresh_packages_list(current_filter[0](current_filter[1]))

def on_ManagerRefreshButton_clicked(*args):
	ManagerWindow.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
	while Gtk.events_pending():
		Gtk.main_iteration()
	transaction.refresh()

def on_history_item_activate(*args):
	with open('/var/log/pamac.log', 'r') as logfile:
		data = logfile.read()
	history_buffer.set_text(data)
	HistoryWindow.show()

def on_history_textview_size_allocate(*args):
	#auto-scrolling method
	adj = history_textview.get_vadjustment()
	adj.set_value(adj.get_upper() - adj.get_page_size())

def on_HistoryCloseButton_clicked(*args):
	HistoryWindow.hide()

def on_HistoryWindow_delete_event(*args):
	HistoryWindow.hide()
	# return True is needed to not destroy the window
	return True

def on_local_item_activate(*args):
	response = PackagesChooserDialog.run()
	if response:
		PackagesChooserDialog.hide()
		while Gtk.events_pending():
			Gtk.main_iteration()

def on_preferences_item_activate(*args):
	transaction.EnableAURButton.set_active(config.enable_aur)
	transaction.RemoveUnrequiredDepsButton.set_active(config.recurse)
	transaction.RefreshPeriodSpinButton.set_value(config.refresh_period)
	transaction.PreferencesWindow.show()

def on_about_item_activate(*args):
	response = AboutDialog.run()
	if response:
		AboutDialog.hide()
		while Gtk.events_pending():
			Gtk.main_iteration()

def on_package_open_button_clicked(*args):
	packages_paths = PackagesChooserDialog.get_filenames()
	if packages_paths:
		PackagesChooserDialog.hide()
		while Gtk.events_pending():
			Gtk.main_iteration()
		for path in packages_paths:
			transaction.to_load.add(path)
		ManagerWindow.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
		while Gtk.events_pending():
			Gtk.main_iteration()
		error = transaction.run()
		ManagerWindow.get_window().set_cursor(None)
		if error:
			handle_error(error)

def on_PackagesChooserDialog_file_activated(*args):
	on_package_open_button_clicked(*args)

def on_package_cancel_button_clicked(*args):
	PackagesChooserDialog.hide()
	while Gtk.events_pending():
		Gtk.main_iteration()

def on_state_column_clicked(column):
	liststore = packages_list_treeview.get_model()
	state_column.set_sort_indicator(True)
	name_column.set_sort_indicator(False)
	version_column.set_sort_indicator(False)
	repo_column.set_sort_indicator(False)
	size_column.set_sort_indicator(False)
	liststore.set_sort_func(0, state_column_sort_func, None)

def on_name_column_clicked(column):
	liststore = packages_list_treeview.get_model()
	state_column.set_sort_indicator(False)
	name_column.set_sort_indicator(True)
	version_column.set_sort_indicator(False)
	repo_column.set_sort_indicator(False)
	size_column.set_sort_indicator(False)
	liststore.set_sort_func(0, name_column_sort_func, None)

def on_version_column_clicked(column):
	liststore = packages_list_treeview.get_model()
	state_column.set_sort_indicator(False)
	name_column.set_sort_indicator(False)
	version_column.set_sort_indicator(True)
	repo_column.set_sort_indicator(False)
	size_column.set_sort_indicator(False)
	liststore.set_sort_func(0, version_column_sort_func, None)

def on_repo_column_clicked(column):
	liststore = packages_list_treeview.get_model()
	state_column.set_sort_indicator(False)
	name_column.set_sort_indicator(False)
	version_column.set_sort_indicator(False)
	repo_column.set_sort_indicator(True)
	size_column.set_sort_indicator(False)
	liststore.set_sort_func(0, repo_column_sort_func, None)

def on_size_column_clicked(column):
	liststore = packages_list_treeview.get_model()
	state_column.set_sort_indicator(False)
	name_column.set_sort_indicator(False)
	version_column.set_sort_indicator(False)
	repo_column.set_sort_indicator(False)
	size_column.set_sort_indicator(True)
	liststore.set_sort_func(0, size_column_sort_func, None)

signals = {'on_ManagerWindow_delete_event' : on_ManagerWindow_delete_event,
		'on_TransValidButton_clicked' : on_TransValidButton_clicked,
		'on_TransCancelButton_clicked' : on_TransCancelButton_clicked,
		'on_ChooseButton_clicked' : transaction.on_ChooseButton_clicked,
		'on_PreferencesCloseButton_clicked' : transaction.on_PreferencesCloseButton_clicked,
		'on_PreferencesWindow_delete_event' : transaction.on_PreferencesWindow_delete_event,
		'on_PreferencesValidButton_clicked' : transaction.on_PreferencesValidButton_clicked,
		'on_progress_textview_size_allocate' : transaction.on_progress_textview_size_allocate,
		'on_choose_renderertoggle_toggled' : transaction.on_choose_renderertoggle_toggled,
		'on_ProgressCancelButton_clicked' : on_ProgressCancelButton_clicked,
		'on_ProgressCloseButton_clicked' : on_ProgressCloseButton_clicked,
		'on_search_entry_icon_press' : on_search_entry_icon_press,
		'on_search_entry_activate' : on_search_entry_activate,
		'on_list_treeview_button_press_event' : on_list_treeview_button_press_event,
		'on_list_treeview_selection_changed' : on_list_treeview_selection_changed,
		'on_search_treeview_selection_changed' : on_search_treeview_selection_changed,
		'on_groups_treeview_selection_changed' : on_groups_treeview_selection_changed,
		'on_states_treeview_selection_changed' : on_states_treeview_selection_changed,
		'on_repos_treeview_selection_changed' : on_repos_treeview_selection_changed,
		'on_list_treeview_row_activated' : on_list_treeview_row_activated,
		'on_notebook1_switch_page' : on_notebook1_switch_page,
		'on_ManagerCancelButton_clicked' : on_ManagerCancelButton_clicked,
		'on_ManagerValidButton_clicked' : on_ManagerValidButton_clicked,
		'on_ManagerRefreshButton_clicked' : on_ManagerRefreshButton_clicked,
		'on_history_item_activate' : on_history_item_activate,
		'on_history_textview_size_allocate' : on_history_textview_size_allocate,
		'on_HistoryCloseButton_clicked' : on_HistoryCloseButton_clicked,
		'on_HistoryWindow_delete_event' : on_HistoryWindow_delete_event,
		'on_local_item_activate' : on_local_item_activate,
		'on_preferences_item_activate' : on_preferences_item_activate,
		'on_about_item_activate' : on_about_item_activate,
		'on_package_open_button_clicked' : on_package_open_button_clicked,
		'on_package_cancel_button_clicked' : on_package_cancel_button_clicked,
		'on_PackagesChooserDialog_file_activated' : on_PackagesChooserDialog_file_activated,
		'on_state_column_clicked' : on_state_column_clicked,
		'on_name_column_clicked' : on_name_column_clicked,
		'on_version_column_clicked' : on_version_column_clicked,
		'on_repo_column_clicked' : on_repo_column_clicked,
		'on_size_column_clicked' : on_size_column_clicked}

def config_dbus_signals():
	bus = dbus.SystemBus()
	bus.add_signal_receiver(handle_reply, dbus_interface = "org.manjaro.pamac", signal_name = "EmitTransactionDone")
	bus.add_signal_receiver(handle_error, dbus_interface = "org.manjaro.pamac", signal_name = "EmitTransactionError")
	bus.add_signal_receiver(handle_updates, dbus_interface = "org.manjaro.pamac", signal_name = "EmitAvailableUpdates")
	bus.add_signal_receiver(reload_config, dbus_interface = "org.manjaro.pamac", signal_name = "EmitReloadConfig")

if common.pid_file_exists():
	transaction.ErrorDialog.format_secondary_text(_('Pamac is already running'))
	response = transaction.ErrorDialog.run()
	if response:
		transaction.ErrorDialog.hide()
else:
	common.write_pid_file()
	interface.connect_signals(signals)
	transaction.get_dbus_methods()
	transaction.config_dbus_signals()
	config_dbus_signals()
	state_column.set_cell_data_func(state_rendererpixbuf, state_column_display_func)
	name_column.set_cell_data_func(name_renderertext, name_column_display_func)
	version_column.set_cell_data_func(version_renderertext, version_column_display_func)
	repo_column.set_cell_data_func(repo_renderertext, repo_column_display_func)
	size_column.set_cell_data_func(size_renderertext, size_column_display_func)
	transaction.get_handle()
	update_lists()
	ManagerWindow.show()
	#ManagerWindow.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
	#transaction.refresh()
	while Gtk.events_pending():
		Gtk.main_iteration()
	Gtk.main()
