import Reflux from 'reflux';
import _ from 'lodash';

import ProjectActions from '../actions/projectActions';

const ProjectsStore = Reflux.createStore({
  init() {
    this.reset();
    this.listenTo(ProjectActions.createSuccess, this.onCreateSuccess);
    this.listenTo(ProjectActions.updateSuccess, this.onUpdateSuccess);
    this.listenTo(ProjectActions.loadStatsSuccess, this.onStatsLoadSuccess);
    this.listenTo(ProjectActions.changeSlug, this.onChangeSlug);
  },

  reset() {
    this.itemsById = {};
  },

  loadInitialData(items) {
    this.itemsById = items.reduce((map, project) => {
      map[project.id] = project;
      return map;
    }, {});
    this.trigger(new Set(Object.keys(this.itemsById)));
  },

  onChangeSlug(prevSlug, newSlug) {
    let prevProject = this.getBySlug(prevSlug);

    if (!prevProject) {
      // This shouldn't happen
      return;
    }

    this.itemsById[newSlug] = {
      ...prevProject,
      slug: newSlug,
    };

    this.itemsById = {
      ...this.itemsById,
    };

    // Ideally we'd always trigger this.itemsById, but following existing patterns
    // so we don't break things
    this.trigger(new Set([prevProject.id]));
  },

  onCreateSuccess(project) {
    this.itemsById[project.id] = project;
    this.trigger(new Set([project.id]));
  },

  onUpdateSuccess(data) {
    let project = this.getById(data.id);
    Object.assign(project, data);
    this.trigger(new Set([data.id]));
  },

  onStatsLoadSuccess(data) {
    let touchedIds = [];
    _.each(data || [], (stats, projectId) => {
      if (projectId in this.itemsById) {
        this.itemsById[projectId].stats = stats;
        touchedIds.push(projectId);
      }
    });
    this.trigger(new Set(touchedIds));
  },

  getAll() {
    return Object.values(this.itemsById);
  },

  getAllGroupedByOrganization() {
    return this.getAll().reduce((acc, project) => {
      const orgSlug = project.organization.slug;
      if (acc[orgSlug]) {
        acc[orgSlug].projects.push(project);
      } else {
        acc[orgSlug] = {
          organization: project.organization,
          projects: [project],
        };
      }
      return acc;
    }, {});
  },

  getById(id) {
    return this.getAll().find(project => project.id === id);
  },

  getBySlug(slug) {
    return this.getAll().find(project => project.slug === slug);
  },
});

export default ProjectsStore;
